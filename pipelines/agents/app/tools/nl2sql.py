"""
Ferramenta NL2SQL - Geração e Execução de SQL

Gera queries SQL para buscar dados de market.ohlcv e executa de forma segura.
"""

import asyncio
from datetime import datetime, timedelta

from tools.validators import sanitize_sql_query, validate_sql_query

from llmops_lab.db.connectors import get_async_db
from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


class NL2SQLTool:
    """
    Ferramenta para geração e execução de queries SQL

    Busca dados históricos de OHLCV (Open, High, Low, Close, Volume)
    da tabela market.ohlcv de forma segura e validada.
    """

    def __init__(self):
        self.db = get_async_db()
        self.max_rows = 10000
        self.timeout_seconds = 30

    async def generate_sql(self, ticker: str, period_days: int) -> str:
        """
        Gera query SQL para buscar dados OHLCV

        Args:
            ticker: Código da ação
            period_days: Período em dias

        Returns:
            Query SQL
        """
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=period_days)

        query = f"""
                SELECT
                    ticker,
                    date,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    adjusted_close
                FROM market.ohlcv
                WHERE ticker = '{ticker}'
                AND date >= '{start_date}'
                AND date <= '{end_date}'
                ORDER BY date DESC
                LIMIT {self.max_rows};
                        """.strip()

        logger.info(f"Query SQL gerada para {ticker} ({period_days} dias)")
        return query

    def validate_sql(self, query: str) -> tuple[bool, str]:
        """
        Valida query SQL

        Args:
            query: Query a validar

        Returns:
            Tupla (is_valid, error_message)
        """
        query_sanitized = sanitize_sql_query(query)

        is_valid, error_msg = validate_sql_query(query_sanitized)

        if not is_valid:
            logger.warning(f"SQL validation failed: {error_msg}")
            return False, error_msg

        logger.info("SQL validation passed")
        return True, ""

    async def execute_sql(self, query: str) -> tuple[bool, list[dict] | str]:
        """
        Executa query SQL com timeout

        Args:
            query: Query a executar

        Returns:
            Tupla (success, data_or_error)
        """
        is_valid, error_msg = self.validate_sql(query)
        if not is_valid:
            return False, f"Query inválida: {error_msg}"

        try:
            rows = await asyncio.wait_for(self.db.fetch(query), timeout=self.timeout_seconds)

            if not rows:
                logger.warning("Query retornou 0 linhas")
                return True, []

            data = [dict(row) for row in rows]

            logger.info(f"Query executada com sucesso: {len(data)} linhas retornadas")
            return True, data

        except asyncio.TimeoutError:
            error = f"Query excedeu timeout de {self.timeout_seconds}s"
            logger.error(error)
            return False, error

        except Exception as e:
            error = f"Erro ao executar query: {str(e)}"
            logger.error(error, exc_info=True)
            return False, error

    def format_results(self, rows: list[dict]) -> str:
        """
        Formata resultados para contexto do LLM

        Args:
            rows: Lista de dicionários com dados

        Returns:
            String formatada para análise
        """
        if not rows:
            return "Nenhum dado encontrado para o período especificado."

        ticker = rows[0].get("ticker", "N/A")
        num_rows = len(rows)

        first_row = rows[0]
        last_row = rows[-1]

        summary = f"""
# Dados OHLCV - {ticker}

**Período**: {last_row["date"]} até {first_row["date"]}
**Total de registros**: {num_rows}

## Resumo Estatístico

**Último Fechamento**: R$ {first_row["close"]:.2f}
**Fechamento Inicial**: R$ {last_row["close"]:.2f}
**Variação no Período**: {((first_row["close"] - last_row["close"]) / last_row["close"] * 100):.2f}%

**Máxima do Período**: R$ {max(r["high"] for r in rows):.2f}
**Mínima do Período**: R$ {min(r["low"] for r in rows):.2f}

**Volume Médio**: {sum(r["volume"] for r in rows if r["volume"]) / num_rows:,.0f}
**Volume Total**: {sum(r["volume"] for r in rows if r["volume"]):,.0f}

## Últimas 10 Sessões

| Data | Abertura | Máxima | Mínima | Fechamento | Volume |
|------|----------|--------|--------|------------|--------|
"""

        for row in rows[:10]:
            date = row["date"]
            open_price = row["open"] or 0
            high = row["high"] or 0
            low = row["low"] or 0
            close = row["close"] or 0
            volume = row["volume"] or 0

            summary += f"| {date} | R$ {open_price:.2f} | R$ {high:.2f} | R$ {low:.2f} | R$ {close:.2f} | {volume:,.0f} |\n"

        summary += f"\n**Observação**: Mostrando as 10 sessões mais recentes de um total de {num_rows} registros."

        return summary.strip()

    async def analyze_ticker(self, ticker: str, period_days: int) -> dict:
        """
        Executa análise completa de um ticker

        Args:
            ticker: Código da ação
            period_days: Período em dias

        Returns:
            Dicionário com resultados
        """
        start_time = datetime.now()

        query = await self.generate_sql(ticker, period_days)

        success, result = await self.execute_sql(query)

        if not success:
            return {
                "success": False,
                "error": result,
                "ticker": ticker,
                "period_days": period_days,
                "execution_time_ms": int((datetime.now() - start_time).total_seconds() * 1000),
            }

        if not isinstance(result, list):
            return {
                "success": False,
                "error": "Resultado inválido da query",
                "ticker": ticker,
                "period_days": period_days,
                "execution_time_ms": int((datetime.now() - start_time).total_seconds() * 1000),
            }

        formatted_data = self.format_results(result)

        execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        return {
            "success": True,
            "ticker": ticker,
            "period_days": period_days,
            "data_points": len(result),
            "raw_data": result,
            "formatted_data": formatted_data,
            "query": query,
            "execution_time_ms": execution_time_ms,
        }
