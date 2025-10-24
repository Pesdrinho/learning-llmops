"""Extractor de dividendos"""

from datetime import datetime
from typing import Any

from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


async def extract_dividends(data: dict[str, Any]) -> list[dict]:
    """
    Extrai dados de dividendos da resposta da API

    Args:
        data: Resposta da API Brapi

    Returns:
        Lista de dividendos
    """
    results = data.get("results", [])
    dividends = []

    for result in results:
        ticker = result.get("symbol")
        dividends_data = result.get("dividendsData", {})
        cash_dividends = dividends_data.get("cashDividends", [])

        for dividend in cash_dividends:
            try:
                dividend_record = {
                    "ticker": ticker,
                    "date": datetime.strptime(dividend.get("date"), "%Y-%m-%d").date(),
                    "type": dividend.get("type", "dividend"),
                    "value": dividend.get("rate"),
                    "currency": "BRL",
                    "payment_date": datetime.strptime(dividend.get("paymentDate"), "%Y-%m-%d").date() if dividend.get("paymentDate") else None,
                }

                dividends.append(dividend_record)

            except Exception as e:
                logger.error(f"Erro ao processar dividend {ticker}: {e}")
                continue

    logger.info(f"Extraídos {len(dividends)} dividendos")
    return dividends




