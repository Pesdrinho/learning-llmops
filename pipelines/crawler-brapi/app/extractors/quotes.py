"""Extractor de cotações de ações"""

from datetime import datetime
from typing import Any

from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


async def extract_quotes(data: dict[str, Any]) -> list[dict]:
    """
    Extrai dados de cotações da resposta da API

    Args:
        data: Resposta da API Brapi

    Returns:
        Lista de cotações processadas
    """
    results = data.get("results", [])
    quotes = []

    for result in results:
        try:
            # Extrai asset info
            asset = {
                "ticker": result.get("symbol"),
                "name": result.get("longName") or result.get("shortName"),
                "sector": result.get("sector"),
                "industry": result.get("industry"),
                "asset_type": result.get("type", "stock"),
                "currency": result.get("currency", "BRL"),
                "metadata": {
                    "market_cap": result.get("marketCap"),
                    "regular_market_volume": result.get("regularMarketVolume"),
                    "average_daily_volume_10_day": result.get("averageDailyVolume10Day"),
                },
            }

            # Extrai quote atual
            quote = {
                "ticker": result.get("symbol"),
                "date": datetime.now().date(),
                "open": result.get("regularMarketOpen"),
                "high": result.get("regularMarketDayHigh"),
                "low": result.get("regularMarketDayLow"),
                "close": result.get("regularMarketPrice"),
                "volume": result.get("regularMarketVolume"),
                "adjusted_close": result.get("regularMarketPrice"),
            }

            quotes.append({"asset": asset, "quote": quote})

        except Exception as e:
            logger.error(f"Erro ao processar quote {result.get('symbol')}: {e}")
            continue

    logger.info(f"Extraídas {len(quotes)} cotações")
    return quotes
