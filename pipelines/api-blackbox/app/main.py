"""
API Blackbox - Aplicação Principal (FastAPI)

Este é o ponto de entrada da aplicação. Aqui definimos:
- Configuração do FastAPI
- Middlewares (CORS, PII, Cost limiting)
- Rotas/Endpoints
- Tratamento de erros
- Documentação automática

FastAPI: Framework web moderno para construir APIs com Python
Características:
- Performance: Tão rápido quanto NodeJS/Go
- Tipo-seguro: Validação automática via Pydantic
- Documentação automática: Swagger UI + ReDoc
- Async nativo: Suporta await/async
- Fácil de usar: Sintaxe limpa e intuitiva

Arquitetura da aplicação:

    Client → [CORS Middleware]
           → [Cost Limit Middleware]
           → [Endpoint /chat]
           → [PII Masking]
           → [OpenRouter Client]
           → [LLM]
           → [Response + Logging]
           → Client
"""

import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from llmops_lab.db.connectors import get_async_db
from llmops_lab.logging.logger import get_logger

from .middleware.cost_limiter import CostLimiter, cost_limit_middleware
from .middleware.pii_masker import masker
from .models import (
    ChatRequest,
    ChatResponse,
    ErrorDetail,
    HealthResponse,
    ModelInfo,
    ModelsResponse,
)
from .router import OpenRouterClient

# ========== CONFIGURAÇÃO ==========

logger = get_logger(__name__)

# Versão da API (versionamento semântico)
API_VERSION = "0.1.0"


# ========== LIFECYCLE EVENTS ==========

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação

    Lifecycle Events no FastAPI:
    - startup: Executado quando a aplicação inicia
    - shutdown: Executado quando a aplicação fecha

    Use para:
    - Conectar ao banco de dados
    - Inicializar caches
    - Carregar modelos ML
    - Configurar recursos que devem persistir durante toda a execução

    Exemplo de execução:
        Startup → API rodando → Shutdown
    """
    # ========== STARTUP ==========
    logger.info("=" * 80)
    logger.info("🚀 Iniciando API Blackbox")
    logger.info(f"Versão: {API_VERSION}")
    logger.info("=" * 80)

    # Inicializa recursos
    try:
        # Testa conexão com banco
        db = get_async_db()
        await db.connect()
        logger.info("✅ Banco de dados conectado")
        await db.disconnect()

        # Testa OpenRouter
        async with OpenRouterClient():
            logger.info("✅ OpenRouter client inicializado")

        logger.info("🎉 API Blackbox pronta para receber requisições!")

    except Exception as e:
        logger.error(f"❌ Erro na inicialização: {e}")
        raise

    # Yield = ponto onde a aplicação roda
    yield

    # ========== SHUTDOWN ==========
    logger.info("🛑 Encerrando API Blackbox...")
    logger.info("Cleanup concluído. Até logo! 👋")


# ========== APLICAÇÃO FASTAPI ==========

app = FastAPI(
    title="API Blackbox - Gateway OpenRouter",
    description="""
    API Gateway para modelos LLM via OpenRouter.

    **Funcionalidades:**
    - 🤖 Acesso a múltiplos modelos LLM (GPT, Claude, Llama, etc)
    - 🔒 Mascaramento automático de PII (CPF, CNPJ, email, telefone)
    - 💰 Controle de custos com limite diário configurável
    - 📊 Logging completo de todas as interações
    - 🚀 Performance otimizada com async/await

    **Documentação Interativa:**
    - Swagger UI: /docs
    - ReDoc: /redoc
    """,
    version=API_VERSION,
    lifespan=lifespan,  # Lifecycle handler
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc
)


# ========== MIDDLEWARES ==========

# CORS - Cross-Origin Resource Sharing
# Permite que frontend (ex: React) em outro domínio acesse a API
#
# Por que CORS?
# - Browsers bloqueiam requests entre domínios diferentes (segurança)
# - CORS configura quais domínios podem acessar
#
# Exemplo:
#   Frontend: http://localhost:3000
#   Backend: http://localhost:8000
#   Sem CORS: Bloqueado ❌
#   Com CORS: Permitido ✅
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Prod = domínios específicos
    allow_credentials=True,
    allow_methods=["*"],  # GET, POST, PUT, DELETE, etc
    allow_headers=["*"],  # Authorization, Content-Type, etc
)

# Cost Limit Middleware
# Verifica se cliente está dentro do limite diário antes de processar
app.middleware("http")(cost_limit_middleware)


# ========== TRATAMENTO DE ERROS GLOBAL ==========

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Tratador global de HTTPException

    Padroniza formato de erro para todas as respostas HTTP de erro.

    Args:
        request: Request que causou o erro
        exc: Exceção levantada

    Returns:
        JSONResponse com erro formatado
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorDetail(
            error=exc.detail,
            message=str(exc.detail),
            request_id=str(uuid.uuid4())
        ).model_dump()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Tratador global de exceções não capturadas

    Captura QUALQUER exceção que não foi tratada antes.
    Importante para não vazar informações sensíveis em stack traces.

    Args:
        request: Request que causou o erro
        exc: Exceção levantada

    Returns:
        JSONResponse com erro 500
    """
    logger.error(f"Erro não tratado: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorDetail(
            error="internal_server_error",
            message="Erro interno do servidor. Entre em contato com o suporte.",
            request_id=str(uuid.uuid4())
        ).model_dump()
    )


# ========== ENDPOINTS ==========

@app.get(
    "/",
    summary="Root endpoint",
    description="Retorna informações básicas da API"
)
async def root():
    """
    Endpoint raiz - informações da API

    Returns:
        Informações básicas da API

    Exemplo:
        GET /

        Response:
        {
            "name": "API Blackbox",
            "version": "0.1.0",
            "status": "running",
            "docs": "/docs"
        }
    """
    return {
        "name": "API Blackbox - OpenRouter Gateway",
        "version": API_VERSION,
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "chat": "/chat",
            "models": "/models",
            "health": "/health"
        }
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Verifica saúde da API e dependências"
)
async def health_check():
    """
    Health check endpoint

    Usado por:
    - Load balancers (verificar se servidor está vivo)
    - Monitoramento (Datadog, New Relic, etc)
    - Kubernetes (liveness/readiness probes)

    Verifica:
    - API está respondendo
    - Banco de dados está acessível
    - OpenRouter está acessível

    Returns:
        HealthResponse com status de cada componente

    Status:
        - healthy: Tudo OK ✅
        - degraded: Algum serviço com problema, mas API funcional ⚠️
        - unhealthy: API não pode funcionar ❌

    Exemplo:
        GET /health

        Response:
        {
            "status": "healthy",
            "version": "0.1.0",
            "timestamp": "2024-01-15T10:30:00Z",
            "checks": {
                "database": "ok",
                "openrouter": "ok"
            }
        }
    """
    checks = {}
    overall_status = "healthy"

    # Verifica banco de dados
    try:
        db = get_async_db()
        await db.connect()
        await db.disconnect()
        checks["database"] = "ok"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database"] = f"error: {str(e)}"
        overall_status = "degraded"

    # Verifica OpenRouter (apenas se API key configurada)
    try:
        async with OpenRouterClient():
            checks["openrouter"] = "ok"
    except ValueError:
        # API key não configurada
        checks["openrouter"] = "not_configured"
        overall_status = "degraded"
    except Exception as e:
        logger.error(f"OpenRouter health check failed: {e}")
        checks["openrouter"] = f"error: {str(e)}"
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        version=API_VERSION,
        timestamp=datetime.now(),
        checks=checks
    )


@app.get(
    "/models",
    response_model=ModelsResponse,
    summary="Listar modelos disponíveis",
    description="Retorna lista de modelos LLM disponíveis via OpenRouter"
)
async def list_models():
    """
    Lista modelos LLM disponíveis

    Retorna informações sobre cada modelo:
    - Nome e ID
    - Provider (OpenAI, Anthropic, etc)
    - Preços (input/output por 1k tokens)
    - Tamanho do contexto
    - Descrição

    Útil para:
    - Cliente escolher modelo adequado
    - Comparar preços
    - Verificar capacidades

    Returns:
        ModelsResponse com lista de modelos

    Exemplo:
        GET /models

        Response:
        {
            "models": [
                {
                    "id": "gpt-oss-120b",
                    "name": "GPT OSS 120B",
                    "provider": "Together",
                    "input_cost_per_1k": 0.10,
                    "output_cost_per_1k": 0.20,
                    "context_window": 4096,
                    "description": "Modelo open-source econômico"
                },
                ...
            ],
            "total": 5
        }
    """
    # Lista hardcoded de modelos principais
    # Em produção, poderia buscar dinamicamente do OpenRouter
    # via endpoint /api/v1/models

    models = [
        ModelInfo(
            id="gpt-oss-120b",
            name="GPT OSS 120B",
            provider="Together",
            input_cost_per_1k=0.10,
            output_cost_per_1k=0.20,
            context_window=4096,
            description="Modelo open-source econômico e rápido, ideal para tarefas gerais"
        ),
        ModelInfo(
            id="anthropic/claude-3.5-sonnet",
            name="Claude 3.5 Sonnet",
            provider="Anthropic",
            input_cost_per_1k=3.00,
            output_cost_per_1k=15.00,
            context_window=200000,
            description="Modelo premium da Anthropic, excelente para tarefas complexas e contextos longos"
        ),
        ModelInfo(
            id="openai/gpt-4-turbo",
            name="GPT-4 Turbo",
            provider="OpenAI",
            input_cost_per_1k=10.00,
            output_cost_per_1k=30.00,
            context_window=128000,
            description="GPT-4 otimizado, alta performance para tarefas complexas"
        ),
        ModelInfo(
            id="openai/gpt-3.5-turbo",
            name="GPT-3.5 Turbo",
            provider="OpenAI",
            input_cost_per_1k=0.50,
            output_cost_per_1k=1.50,
            context_window=16385,
            description="Modelo econômico da OpenAI, bom custo-benefício"
        ),
        ModelInfo(
            id="meta-llama/llama-3-70b-instruct",
            name="Llama 3 70B Instruct",
            provider="Meta",
            input_cost_per_1k=0.70,
            output_cost_per_1k=0.90,
            context_window=8192,
            description="Modelo open-source da Meta, bom para instruction following"
        ),
    ]

    return ModelsResponse(
        models=models,
        total=len(models)
    )


@app.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat completion",
    description="Envia mensagens para um modelo LLM e recebe resposta",
    responses={
        200: {"description": "Resposta gerada com sucesso"},
        400: {"description": "Request inválido"},
        429: {"description": "Limite diário de custo excedido"},
        500: {"description": "Erro interno do servidor"}
    }
)
async def chat_completion(request: ChatRequest, http_request: Request):
    """
    Endpoint principal - Chat completion

    Este é o coração da API. Processo completo:

    1. Recebe requisição com mensagens
    2. Mascara PII nas mensagens
    3. Envia para OpenRouter
    4. Recebe resposta
    5. Calcula custo
    6. Registra log no banco
    7. Retorna resposta mascarada

    Args:
        request: ChatRequest com mensagens e parâmetros
        http_request: Request HTTP (injetado pelo FastAPI)

    Returns:
        ChatResponse com resposta do modelo

    Raises:
        HTTPException 400: Request inválido
        HTTPException 429: Limite de custo excedido
        HTTPException 500: Erro no processamento

    Exemplo:
        POST /chat
        {
            "messages": [
                {"role": "user", "content": "Qual a cotação da PETR4?"}
            ],
            "model": "gpt-oss-120b",
            "temperature": 0.7
        }

        Response:
        {
            "message": {
                "role": "assistant",
                "content": "A cotação atual da PETR4 é..."
            },
            "model": "gpt-oss-120b",
            "usage": {
                "prompt_tokens": 15,
                "completion_tokens": 30,
                "total_tokens": 45
            },
            "cost_usd": 0.0075,
            "latency_ms": 1234,
            "created_at": "2024-01-15T10:30:00Z",
            "request_id": "uuid-here"
        }
    """
    # Inicia timer para latência
    start_time = time.time()

    # Gera ID único para a requisição (rastreamento)
    request_id = str(uuid.uuid4())

    # Extrai API key do header
    api_key = http_request.headers.get("Authorization", "").replace("Bearer ", "")

    logger.info(f"[{request_id}] Iniciando chat completion | Modelo: {request.model}")

    try:
        # ========== 1. MASCARA PII NAS MENSAGENS ==========
        # Importante: mascara ANTES de enviar ao LLM
        # Assim, o LLM nunca vê dados sensíveis

        masked_messages = []

        for msg in request.messages:
            # Detecta se há PII
            if masker.has_pii(msg.content):
                logger.warning(
                    f"[{request_id}] PII detectado: "
                    f"{masker.detect_pii_types(msg.content)}"
                )

            # Mascara conteúdo
            masked_content = masker.mask(msg.content)

            # Cria nova mensagem mascarada
            masked_msg = msg.model_copy(update={"content": masked_content})
            masked_messages.append(masked_msg)

        # Atualiza request com mensagens mascaradas
        request.messages = masked_messages

        # ========== 2. CHAMA OPENROUTER ==========

        async with OpenRouterClient() as client:
            # Faz request
            response = await client.chat_completion(request)

            # Extrai dados da resposta
            usage = client.extract_usage(response)
            message = client.extract_message(response)

        # ========== 3. CALCULA CUSTO ==========

        limiter = CostLimiter()
        cost_usd = limiter.calculate_cost(
            model=request.model,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens
        )

        # ========== 4. REGISTRA LOG NO BANCO ==========

        db = get_async_db()
        await db.connect()

        # Log da interação
        log_query = """
            INSERT INTO observability.llm_logs (
                user_id, model, provider,
                prompt_masked, response_masked,
                input_tokens, output_tokens, cost_usd,
                latency_ms, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """

        # Concatena mensagens mascaradas para o log
        prompt_text = "\n".join([f"{m.role}: {m.content}" for m in masked_messages])
        response_text = message.content

        latency_ms = int((time.time() - start_time) * 1000)

        async with db.pool.acquire() as conn:
            await conn.execute(
                log_query,
                request.user_id or "anonymous",
                request.model,
                "openrouter",
                prompt_text,
                response_text,
                usage.prompt_tokens,
                usage.completion_tokens,
                cost_usd,
                latency_ms,
                "success"
            )

        # Registra custo
        await limiter.record_spend(
            api_key=api_key or None,
            model=request.model,
            cost_usd=cost_usd,
            db=db
        )

        await db.disconnect()

        # ========== 5. RETORNA RESPOSTA ==========

        logger.info(
            f"[{request_id}] Chat completion concluído | "
            f"Tokens: {usage.total_tokens} | "
            f"Custo: ${cost_usd:.6f} | "
            f"Latência: {latency_ms}ms"
        )

        return ChatResponse(
            message=message,
            model=request.model,
            usage=usage,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            created_at=datetime.now(),
            request_id=request_id
        )

    except Exception as e:
        # Log do erro
        latency_ms = int((time.time() - start_time) * 1000)

        logger.error(
            f"[{request_id}] Erro no chat completion: {e}",
            exc_info=True
        )

        # Tenta registrar erro no banco
        try:
            db = get_async_db()
            await db.connect()

            log_query = """
                INSERT INTO observability.llm_logs (
                    user_id, model, provider,
                    prompt_masked, response_masked,
                    latency_ms, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """

            async with db.pool.acquire() as conn:
                await conn.execute(
                    log_query,
                    request.user_id or "anonymous",
                    request.model,
                    "openrouter",
                    "error",
                    str(e),
                    latency_ms,
                    "error"
                )

            await db.disconnect()
        except Exception as log_e:
            pass  # Se logging falhar, não quebra a resposta de erro

        # Levanta HTTPException
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) from e


# ========== MAIN (para execução local) ==========

if __name__ == "__main__":
    import uvicorn

    # Roda servidor de desenvolvimento
    # Para produção, use: gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Hot reload em desenvolvimento
        log_level="info"
    )

