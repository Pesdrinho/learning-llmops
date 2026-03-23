"""
Agents Pipeline - Aplicação Principal (FastAPI)

API para geração de análises de ações usando agentes inteligentes com LangGraph.
"""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from config import get_config
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from models import ErrorDetail, HealthResponse
from routes.analysis import router as analysis_router

from llmops_lab.db.connectors import get_async_db
from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)

API_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação

    Startup:
    - Conecta ao banco de dados
    - Inicializa grafo de agentes
    - Valida configurações

    Shutdown:
    - Fecha conexões
    - Cleanup de recursos
    """
    logger.info("=" * 80)
    logger.info("🤖 Iniciando Agents Pipeline")
    logger.info(f"Versão: {API_VERSION}")
    logger.info("=" * 80)

    try:
        db = get_async_db()
        await db.connect()
        logger.info("✅ Banco de dados conectado")

        config = get_config()
        logger.info(f"✅ Configuração carregada (env: {config.app_env})")

        from graph.builder import get_agent_graph

        graph = get_agent_graph()
        logger.info("✅ Grafo de agentes inicializado")

        logger.info("🎉 Agents Pipeline pronto para receber requisições!")

    except Exception as e:
        logger.error(f"❌ Erro na inicialização: {e}")
        raise

    yield

    logger.info("🛑 Encerrando Agents Pipeline...")

    db = get_async_db()
    await db.disconnect()

    logger.info("Cleanup concluído. Até logo! 👋")


app = FastAPI(
    title="Agents Pipeline - Análise de Ações",
    description="""
    Pipeline de agentes para análise de ações da B3.

    **Funcionalidades:**
    - 🤖 Agentes inteligentes com LangGraph
    - 📊 Análise técnica baseada em dados reais (OHLCV)
    - 🔍 Busca web para contexto de mercado
    - 💾 Exportação para arquivo e banco de dados
    - 📈 5 tipos de análise: movimentação de preço, volume, tendências, suportes/resistências, comparativa

    **Arquitetura:**
    - NL2SQL: Busca dados históricos de market.ohlcv
    - WebSearch: Busca informações complementares
    - LangGraph: Orquestra execução dos agentes
    - Synthesis: LLM gera análise final

    **Documentação Interativa:**
    - Swagger UI: /docs
    - ReDoc: /redoc
    """,
    version=API_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(analysis_router, tags=["Analysis"])


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Tratador global de HTTPException"""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorDetail(
            error=exc.detail, message=str(exc.detail), request_id=str(uuid.uuid4())
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Tratador global de exceções não capturadas"""
    logger.error(f"Erro não tratado: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorDetail(
            error="internal_server_error",
            message="Erro interno do servidor. Entre em contato com o suporte.",
            request_id=str(uuid.uuid4()),
        ).model_dump(),
    )


@app.get("/", summary="Root endpoint", description="Retorna informações básicas da API")
async def root():
    """
    Endpoint raiz - informações da API

    Returns:
        Informações básicas da API
    """
    return {
        "name": "Agents Pipeline - Análise de Ações",
        "version": API_VERSION,
        "status": "running",
        "architecture": "agents",
        "docs": "/docs",
        "endpoints": {
            "generate_analysis": "/generate_analysis",
            "list_analyses": "/analyses",
            "get_analysis": "/analyses/{id}",
            "stats": "/stats",
            "health": "/health",
        },
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Verifica saúde da API e dependências",
)
async def health_check():
    """
    Health check endpoint

    Verifica:
    - API está respondendo
    - Banco de dados está acessível
    - Grafo de agentes está disponível

    Returns:
        HealthResponse com status de cada componente
    """
    checks = {}
    overall_status = "healthy"

    try:
        db = get_async_db()
        async with db.pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database"] = f"error: {str(e)}"
        overall_status = "degraded"

    try:
        from graph.builder import get_agent_graph

        graph = get_agent_graph()
        checks["agent_graph"] = "ok"
    except Exception as e:
        logger.error(f"Agent graph health check failed: {e}")
        checks["agent_graph"] = f"error: {str(e)}"
        overall_status = "unhealthy"

    try:
        config = get_config()
        if config.openrouter_api_key:
            checks["openrouter_config"] = "ok"
        else:
            checks["openrouter_config"] = "not_configured"
            overall_status = "degraded"
    except Exception as e:
        logger.error(f"Config health check failed: {e}")
        checks["openrouter_config"] = f"error: {str(e)}"
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status, version=API_VERSION, timestamp=datetime.now(), checks=checks
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=9001,
        reload=True,
        log_level="info",
    )
