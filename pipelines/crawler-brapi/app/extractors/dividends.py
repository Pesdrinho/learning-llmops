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
                # Validação defensiva para campos de data
                date_str = dividend.get("date")
                payment_date_str = dividend.get("paymentDate")

                if not date_str:
                    logger.warning(f"Dividendo {ticker} sem data, pulando...")
                    continue

                # Parse da data principal
                try:
                    parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    logger.warning(f"Data inválida para {ticker}: {date_str}, pulando...")
                    continue

                # Parse da data de pagamento (opcional)
                parsed_payment_date = None
                if payment_date_str and payment_date_str:
                    try:
                        parsed_payment_date = datetime.strptime(payment_date_str, "%Y-%m-%d").date()
                    except ValueError:
                        logger.warning(
                            f"Data de pagamento inválida para {ticker}: {payment_date_str}"
                        )

                dividend_record = {
                    "ticker": ticker,
                    "date": parsed_date,
                    "type": dividend.get("type", "dividend"),
                    "value": dividend.get("rate"),
                    "currency": "BRL",
                    "payment_date": parsed_payment_date,
                }

                dividends.append(dividend_record)

            except Exception as e:
                logger.error(f"Erro ao processar dividend {ticker}: {e}")
                continue

    logger.info(f"Extraídos {len(dividends)} dividendos")
    return dividends
