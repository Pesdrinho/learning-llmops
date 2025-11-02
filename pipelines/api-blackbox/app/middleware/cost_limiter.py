"""
Middleware de Controle de Custos e Rate Limiting

Por que controlar custos?
1. **Proteção Financeira**: LLMs custam por uso (pay-per-token)
2. **Prevenção de Abuso**: Evita loops infinitos ou ataques
3. **Orçamento Previsível**: Define teto de gastos diário
4. **Governança**: Rastreamento detalhado de custos

Como funciona?
    Request → Verifica gasto do dia → Se < limite → Processa
                                    → Se >= limite → Retorna 429

Após processamento → Calcula custo → Registra em spend_ledger

Estrutura do banco:
    spend_ledger:
        - api_key_hash: Hash SHA256 da API key (segurança)
        - model: Modelo usado
        - cost_usd: Custo em dólares
        - ts: Timestamp da requisição
"""

import hashlib
import os
from decimal import Decimal

import yaml
from fastapi import Request
from fastapi.responses import JSONResponse

from llmops_lab.db.connectors import AsyncDatabaseConnection, get_async_db
from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


class CostLimiter:
    """
    Gerenciador de custos com limite diário

    Responsabilidades:
    - Verificar se gasto diário está abaixo do limite
    - Calcular custo de requisições
    - Registrar gastos no banco
    - Bloquear requisições se limite excedido
    - Suportar limites diferenciados por tipo de inferência

    Atributos:
        daily_limit_usd: Limite diário em dólares (padrão: US$15)
        model_prices: Dicionário com preços por modelo
        inference_limits: Limites por tipo de inferência
    """

    def __init__(
        self,
        daily_limit_usd: float = 15.0,
        chat_limit_usd: float | None = None,
        dataset_limit_usd: float | None = None,
    ):
        """
        Inicializa o controlador de custos

        Args:
            daily_limit_usd: Limite máximo de gasto diário em USD
            chat_limit_usd: Limite específico para chat completion (None = usa daily_limit)
            dataset_limit_usd: Limite específico para dataset generation (None = usa daily_limit)

        Exemplo:
            >>> limiter = CostLimiter(
            ...     daily_limit_usd=20.0,
            ...     chat_limit_usd=10.0,
            ...     dataset_limit_usd=15.0
            ... )
        """
        self.daily_limit_usd = daily_limit_usd
        self.model_prices = self._load_model_prices()

        self.inference_limits = {
            "chat_completion": chat_limit_usd or daily_limit_usd,
            "dataset_generation": dataset_limit_usd or daily_limit_usd,
            "default": daily_limit_usd,
        }

        logger.info(
            f"CostLimiter inicializado com limites: "
            f"Geral=${daily_limit_usd}, "
            f"Chat=${self.inference_limits['chat_completion']}, "
            f"Dataset=${self.inference_limits['dataset_generation']}"
        )

    def _load_model_prices(self) -> dict:
        """
        Carrega preços dos modelos do arquivo models.yaml

        O arquivo models.yaml contém:
        - Preço por 1k tokens de entrada
        - Preço por 1k tokens de saída
        - Metadados de cada modelo

        Retorna um dicionário para lookup rápido.

        Returns:
            Dicionário {model_id: {in_usd_per_1k, out_usd_per_1k}}

        Exemplo de retorno:
            {
                "openai/gpt-4o-mini": {
                    "in_usd_per_1k": 0.10,
                    "out_usd_per_1k": 0.20
                },
                "anthropic/claude-3.5-sonnet": {
                    "in_usd_per_1k": 3.00,
                    "out_usd_per_1k": 15.00
                }
            }
        """
        try:
            # Caminho para o arquivo de configuração
            # Tenta múltiplos caminhos para compatibilidade local e Docker
            possible_paths = [
                "/app/llmops_lab/config/models.yaml",  # Docker
                os.path.join(
                    os.path.dirname(__file__), "../../../llmops_lab/config/models.yaml"
                ),  # Local
            ]

            config_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    config_path = path
                    break

            if not config_path:
                raise FileNotFoundError(f"models.yaml não encontrado. Tentou: {possible_paths}")

            # Lê o YAML
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)

            # Extrai apenas preços do OpenRouter
            openrouter_models = config.get("openrouter", {})

            logger.info(f"Carregados preços de {len(openrouter_models)} modelos")
            return openrouter_models

        except Exception as e:
            logger.error(f"Erro ao carregar preços dos modelos: {e}")
            # Fallback: preços padrão para não quebrar a API (modelos comuns)
            return {
                "openai/gpt-4o-mini": {"in_usd_per_1k": 0.00015, "out_usd_per_1k": 0.0006},
                "anthropic/claude-3.5-sonnet": {"in_usd_per_1k": 0.003, "out_usd_per_1k": 0.015},
                "meta-llama/llama-3.1-8b-instruct": {
                    "in_usd_per_1k": 0.00005,
                    "out_usd_per_1k": 0.00005,
                },
            }

    def calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Calcula o custo de uma requisição

        Fórmula:
            custo_input = (prompt_tokens / 1000) × preço_input_por_1k
            custo_output = (completion_tokens / 1000) × preço_output_por_1k
            custo_total = custo_input + custo_output

        Args:
            model: Identificador do modelo (ex: "openai/gpt-4o-mini")
            prompt_tokens: Quantidade de tokens na entrada
            completion_tokens: Quantidade de tokens na saída

        Returns:
            Custo total em dólares (float)

        Exemplo:
            >>> limiter = CostLimiter()
            >>> custo = limiter.calculate_cost(
            ...     model="openai/gpt-4o-mini",
            ...     prompt_tokens=1000,  # 1k tokens
            ...     completion_tokens=500  # 0.5k tokens
            ... )
            >>> print(f"${custo:.4f}")
            $0.2000  # (1000/1000 * 0.10) + (500/1000 * 0.20)
        """
        # Busca preços do modelo
        if model not in self.model_prices:
            logger.warning(f"Modelo {model} não encontrado em models.yaml, usando default")
            # Usa preços conservadores para modelos desconhecidos
            price_in = 0.10
            price_out = 0.20
        else:
            price_in = self.model_prices[model].get("in_usd_per_1k", 0.10)
            price_out = self.model_prices[model].get("out_usd_per_1k", 0.20)

        # Calcula custo
        # Conversão para Decimal para precisão financeira
        # Float pode ter erros de arredondamento em cálculos financeiros
        cost_input = Decimal(str(prompt_tokens)) / Decimal("1000") * Decimal(str(price_in))
        cost_output = Decimal(str(completion_tokens)) / Decimal("1000") * Decimal(str(price_out))

        total_cost = float(cost_input + cost_output)

        logger.debug(
            f"Custo calculado: {prompt_tokens} in + {completion_tokens} out = ${total_cost:.6f}"
        )

        return total_cost

    def _hash_api_key(self, api_key: str | None) -> str:
        """
        Gera hash SHA256 da API key

        Por que hash?
        - **Segurança**: Não armazena chaves em texto claro
        - **GDPR/LGPD**: Pseudo-anonimização
        - **Auditoria**: Permite rastrear uso sem expor chaves

        SHA256 é one-way: hash → não dá para recuperar a chave original

        Args:
            api_key: Chave da API (ou None)

        Returns:
            Hash SHA256 hexadecimal

        Exemplo:
            >>> limiter = CostLimiter()
            >>> hash1 = limiter._hash_api_key("my-secret-key")
            >>> hash2 = limiter._hash_api_key("my-secret-key")
            >>> hash1 == hash2  # Sempre o mesmo hash para mesma key
            True
            >>> len(hash1)
            64  # SHA256 = 64 caracteres hex
        """
        if not api_key:
            api_key = "anonymous"

        # Cria hash SHA256
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    async def get_daily_spend(
        self, api_key: str | None, db: AsyncDatabaseConnection, inference_type: str | None = None
    ) -> float:
        """
        Obtém o gasto total do dia corrente

        Consulta o banco de dados (spend_ledger) para somar
        todos os gastos do dia para esta API key.

        Query SQL executada:
            SELECT SUM(cost_usd)
            FROM observability.spend_ledger
            WHERE api_key_hash = ?
              AND ts >= CURRENT_DATE
              AND (inference_type = ? OR inference_type IS NULL)

        Args:
            api_key: Chave da API (será hasheada)
            db: Conexão com banco de dados
            inference_type: Tipo de inferência para filtrar (None = todos)

        Returns:
            Total gasto hoje em dólares

        Exemplo:
            >>> limiter = CostLimiter()
            >>> db = get_async_db()
            >>> await db.connect()
            >>> gasto = await limiter.get_daily_spend("minha-chave", db)
            >>> print(f"Gasto hoje: ${gasto:.2f}")
            Gasto hoje: $2.35
        """
        api_key_hash = self._hash_api_key(api_key)

        if inference_type:
            query = """
                SELECT COALESCE(SUM(sl.cost_usd), 0) as total
                FROM observability.spend_ledger sl
                LEFT JOIN observability.llm_logs ll ON ll.model = sl.model AND DATE(ll.ts) = DATE(sl.ts)
                WHERE sl.api_key_hash = $1
                  AND sl.ts >= CURRENT_DATE
                  AND (ll.inference_type = $2 OR ll.inference_type IS NULL)
            """
            params = (api_key_hash, inference_type)
        else:
            query = """
                SELECT COALESCE(SUM(cost_usd), 0) as total
                FROM observability.spend_ledger
                WHERE api_key_hash = $1
                  AND ts >= CURRENT_DATE
            """
            params = (api_key_hash,)

        try:
            async with db.pool.acquire() as conn:
                result = await conn.fetchrow(query, *params)
                total = float(result["total"]) if result else 0.0

                type_info = f" ({inference_type})" if inference_type else ""
                logger.debug(f"Gasto diário{type_info} para {api_key_hash[:8]}...: ${total:.4f}")
                return total

        except Exception as e:
            logger.error(f"Erro ao consultar gasto diário: {e}")
            # Em caso de erro, assumir gasto = 0 para não bloquear API
            # Em produção, considere bloquear por segurança
            return 0.0

    async def check_limit(
        self,
        api_key: str | None,
        db: AsyncDatabaseConnection,
        estimated_cost: float = 0.0,
        inference_type: str = "default",
    ) -> tuple[bool, float, str]:
        """
        Verifica se a requisição está dentro do limite diário

        Lógica:
        1. Busca gasto atual do dia (por tipo se especificado)
        2. Soma com custo estimado desta requisição
        3. Compara com limite configurado para o tipo
        4. Retorna se pode processar + informações

        Args:
            api_key: Chave da API
            db: Conexão com banco
            estimated_cost: Custo estimado desta requisição (opcional)
            inference_type: Tipo de inferência (chat_completion, dataset_generation, default)

        Returns:
            Tupla (pode_processar, gasto_atual, mensagem)

        Exemplo:
            >>> limiter = CostLimiter(daily_limit_usd=15.0)
            >>> pode, gasto, msg = await limiter.check_limit("chave", db, 0.5)
            >>> if not pode:
            ...     print(f"Bloqueado: {msg}")
            ... else:
            ...     print(f"OK! Gasto atual: ${gasto:.2f}")
        """
        limit_for_type = self.inference_limits.get(inference_type, self.daily_limit_usd)

        current_spend = await self.get_daily_spend(api_key, db, inference_type)

        projected_spend = current_spend + estimated_cost

        if projected_spend >= limit_for_type:
            message = (
                f"Limite diário excedido para {inference_type}. "
                f"Gasto atual: ${current_spend:.2f}, "
                f"Limite: ${limit_for_type:.2f}. "
                f"Limite resetará às 00:00 UTC."
            )
            logger.warning(message)
            return False, current_spend, message

        remaining = limit_for_type - current_spend
        message = (
            f"OK. Tipo: {inference_type}, "
            f"Gasto atual: ${current_spend:.2f}, "
            f"Restante: ${remaining:.2f}"
        )

        return True, current_spend, message

    async def record_spend(
        self, api_key: str | None, model: str, cost_usd: float, db: AsyncDatabaseConnection
    ) -> None:
        """
        Registra um gasto no banco de dados

        Insere um registro na tabela spend_ledger para:
        - Rastreamento de custos
        - Auditoria
        - Geração de relatórios
        - Billing (se necessário)

        Args:
            api_key: Chave da API (será hasheada)
            model: Modelo utilizado
            cost_usd: Custo em dólares
            db: Conexão com banco

        Exemplo:
            >>> limiter = CostLimiter()
            >>> await limiter.record_spend(
            ...     api_key="chave",
            ...     model="openai/gpt-4o-mini",
            ...     cost_usd=0.15,
            ...     db=db
            ... )
        """
        api_key_hash = self._hash_api_key(api_key)

        query = """
            INSERT INTO observability.spend_ledger (api_key_hash, model, cost_usd)
            VALUES ($1, $2, $3)
        """

        try:
            async with db.pool.acquire() as conn:
                await conn.execute(query, api_key_hash, model, cost_usd)

            logger.info(
                f"Gasto registrado: ${cost_usd:.6f} | Modelo: {model} | Hash: {api_key_hash[:8]}..."
            )

        except Exception as e:
            logger.error(f"Erro ao registrar gasto: {e}")
            # Não falha a requisição se logging falhar
            # Em produção, considere retry ou queue


# ========== MIDDLEWARE FASTAPI ==========


async def cost_limit_middleware(request: Request, call_next):
    """
    Middleware FastAPI para verificar limite de custo

    Intercepta TODAS as requisições antes de chegarem
    aos endpoints. Verifica se o cliente está dentro do
    limite diário de gastos.

    Fluxo:
        Request → Middleware → check_limit()
                             ↓
                       Limite OK? → Endpoint → Response
                             ↓
                       Limite excedido? → 429 Too Many Requests

    Args:
        request: Objeto da requisição FastAPI
        call_next: Função para chamar próximo middleware/endpoint

    Returns:
        Response ou JSONResponse com erro 429

    Status Codes:
        200: OK, processado normalmente
        429: Too Many Requests (limite excedido)
        500: Internal Server Error (erro no middleware)
    """
    # Extrai API key do header (se presente)
    # Header padrão: Authorization: Bearer <api_key>
    api_key = request.headers.get("Authorization", "").replace("Bearer ", "")

    # Apenas verifica limite em endpoints de chat
    # Endpoints de saúde/docs não consomem budget
    if request.url.path.startswith("/chat"):
        try:
            # Usa pool global (não cria nova instância)
            db = get_async_db()
            if not db.pool:
                await db.connect()

            # Cria limiter
            budget = float(os.getenv("BUDGET_USD_DAY", "15.0"))
            limiter = CostLimiter(daily_limit_usd=budget)

            # Verifica limite
            can_process, current_spend, message = await limiter.check_limit(
                api_key=api_key or None, db=db
            )

            # Se excedeu limite, retorna 429
            if not can_process:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "rate_limit_exceeded",
                        "message": message,
                        "current_spend_usd": current_spend,
                        "daily_limit_usd": limiter.daily_limit_usd,
                    },
                )

        except Exception as e:
            logger.error(f"Erro no middleware de custo: {e}", exc_info=True)
            # Em caso de erro, permite requisição passar
            # Para não quebrar API por falha de infraestrutura
            # Em produção, considere bloquear por segurança

    # Processa requisição normalmente
    response = await call_next(request)
    return response
