"""
Rastreador de Custos e Rate Limiting
"""

import hashlib
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import yaml
from pydantic import BaseModel

from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


class UsageMetrics(BaseModel):
    """Métricas de uso de um request"""

    input_tokens: int
    output_tokens: int
    model: str
    provider: str


class CostCalculation(BaseModel):
    """Resultado de cálculo de custo"""

    input_cost_usd: Decimal
    output_cost_usd: Decimal
    total_cost_usd: Decimal
    input_tokens: int
    output_tokens: int
    model: str


class CostTracker:
    """Rastreador de custos com rate limiting"""

    def __init__(self, db_connection=None):
        """
        Inicializa o rastreador

        Args:
            db_connection: Conexão com banco de dados (opcional)
        """
        self.db = db_connection
        self._load_pricing()

    def _load_pricing(self):
        """Carrega tabela de preços dos modelos"""
        import os

        config_path = os.path.join(os.path.dirname(__file__), "..", "config", "models.yaml")

        with open(config_path) as f:
            config = yaml.safe_load(f)

        self.pricing = {}

        # Carrega preços dos modelos OpenRouter
        for model_key, model_info in config.get("openrouter", {}).items():
            self.pricing[model_key] = {
                "in_usd_per_1k": model_info["in_usd_per_1k"],
                "out_usd_per_1k": model_info["out_usd_per_1k"],
            }

        # Carrega preços de embeddings
        for model_key, model_info in config.get("embeddings", {}).items():
            self.pricing[model_key] = {
                "in_usd_per_1k": model_info.get("usd_per_1k", 0),
                "out_usd_per_1k": 0,  # Embeddings só cobram input
            }

        # Carrega limites de budget
        self.daily_limit_usd = Decimal(str(config.get("budget", {}).get("daily_limit_usd", 15.0)))
        self.warning_threshold_pct = config.get("budget", {}).get("warning_threshold_pct", 80)

    def calculate_cost(self, metrics: UsageMetrics) -> CostCalculation:
        """
        Calcula custo de um request

        Args:
            metrics: Métricas de uso

        Returns:
            Cálculo detalhado de custo
        """
        model_pricing = self.pricing.get(metrics.model)

        if not model_pricing:
            logger.warning(f"Preço não encontrado para modelo: {metrics.model}. Usando custo zero.")
            model_pricing = {"in_usd_per_1k": 0, "out_usd_per_1k": 0}

        # Calcula custos
        input_cost = Decimal(str(metrics.input_tokens / 1000 * model_pricing["in_usd_per_1k"]))
        output_cost = Decimal(str(metrics.output_tokens / 1000 * model_pricing["out_usd_per_1k"]))
        total_cost = input_cost + output_cost

        return CostCalculation(
            input_cost_usd=input_cost,
            output_cost_usd=output_cost,
            total_cost_usd=total_cost,
            input_tokens=metrics.input_tokens,
            output_tokens=metrics.output_tokens,
            model=metrics.model,
        )

    async def check_daily_limit(self, api_key: str | None = None) -> dict:
        """
        Verifica se o limite diário foi atingido

        Args:
            api_key: API key para tracking (será hasheada)

        Returns:
            Dict com status do limite
        """
        if not self.db:
            logger.warning("DB não configurado, ignorando verificação de limite")
            return {"allowed": True, "spent_today_usd": 0, "limit_usd": float(self.daily_limit_usd)}

        # Hash da API key para privacidade
        api_key_hash = None
        if api_key:
            api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Query para somar gastos do dia
        today = date.today()
        query = """
            SELECT COALESCE(SUM(cost_usd), 0) as total
            FROM observability.spend_ledger
            WHERE DATE(ts) = $1
        """

        params: list[Any] = [today]
        if api_key_hash:
            query += " AND api_key_hash = $2"
            params.append(api_key_hash)

        try:
            result = await self.db.fetchrow(query, *params)
            spent_today = Decimal(str(result["total"]))

            allowed = spent_today < self.daily_limit_usd
            warning = spent_today >= (self.daily_limit_usd * self.warning_threshold_pct / 100)

            return {
                "allowed": allowed,
                "warning": warning,
                "spent_today_usd": float(spent_today),
                "limit_usd": float(self.daily_limit_usd),
                "remaining_usd": float(self.daily_limit_usd - spent_today),
                "usage_pct": float(spent_today / self.daily_limit_usd * 100),
            }
        except Exception as e:
            logger.error(f"Erro ao verificar limite diário: {e}")
            return {"allowed": True, "error": str(e)}

    async def log_usage(
        self,
        cost: CostCalculation,
        api_key: str | None = None,
        user_id: str | None = None,
        prompt: str | None = None,
        response: str | None = None,
        latency_ms: int | None = None,
        status: str = "success",
    ):
        """
        Registra uso no banco de dados

        Args:
            cost: Cálculo de custo
            api_key: API key (será hasheada)
            user_id: ID do usuário
            prompt: Prompt usado (será mascarado)
            response: Resposta gerada (será mascarada)
            latency_ms: Latência em ms
            status: Status do request
        """
        if not self.db:
            logger.warning("DB não configurado, pulando log de uso")
            return

        api_key_hash = None
        if api_key:
            api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        try:
            # Log em llm_logs
            await self.db.execute(
                """
                INSERT INTO observability.llm_logs (
                    ts, user_id, model, provider, prompt_masked, response_masked,
                    input_tokens, output_tokens, cost_usd, latency_ms, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                datetime.now(),
                user_id,
                cost.model,
                "openrouter",  # TODO: extrair provider do model
                prompt[:500] if prompt else None,  # Trunca para segurança
                response[:500] if response else None,
                cost.input_tokens,
                cost.output_tokens,
                float(cost.total_cost_usd),
                latency_ms,
                status,
            )

            # Log em spend_ledger
            await self.db.execute(
                """
                INSERT INTO observability.spend_ledger (
                    ts, api_key_hash, model, cost_usd
                ) VALUES ($1, $2, $3, $4)
                """,
                datetime.now(),
                api_key_hash,
                cost.model,
                float(cost.total_cost_usd),
            )

            logger.info(
                f"Uso registrado: {cost.model} | "
                f"Tokens: {cost.input_tokens}+{cost.output_tokens} | "
                f"Custo: ${cost.total_cost_usd:.4f}"
            )
        except Exception as e:
            logger.error(f"Erro ao registrar uso: {e}")
