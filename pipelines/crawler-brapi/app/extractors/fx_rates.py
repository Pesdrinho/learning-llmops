"""Extractor de taxas de câmbio"""

from datetime import datetime
from typing import Any

from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


async def extract_fx_rates(data: dict[str, Any]) -> list[dict]:
    """
    Extrai taxas de câmbio da resposta da API

    Args:
        data: Resposta da API Brapi

    Returns:
        Lista de taxas de câmbio
    """
    currency = data.get("currency", [])
    fx_rates = []

    for item in currency:
        try:
            # Parse do par de moedas (ex: "USD-BRL")
            currency_pair = item.get("currency", "")
            if "-" in currency_pair:
                base, quote = currency_pair.split("-")
            else:
                logger.warning(f"Formato de moeda inválido: {currency_pair}")
                continue

            fx_rate = {
                "base_currency": base,
                "quote_currency": quote,
                "date": datetime.now().date(),
                "rate": item.get("bidPrice") or item.get("askPrice"),
            }

            fx_rates.append(fx_rate)

        except Exception as e:
            logger.error(f"Erro ao processar taxa de câmbio: {e}")
            continue

    logger.info(f"Extraídas {len(fx_rates)} taxas de câmbio")
    return fx_rates




