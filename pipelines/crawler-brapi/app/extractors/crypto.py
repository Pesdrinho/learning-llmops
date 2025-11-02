"""Extractor de criptomoedas"""

from datetime import datetime
from typing import Any

from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


async def extract_crypto(data: dict[str, Any]) -> list[dict]:
    """
    Extrai dados de criptomoedas da resposta da API

    Args:
        data: Resposta da API Brapi

    Returns:
        Lista de preços de cripto
    """
    coins = data.get("coins", [])
    crypto_prices = []

    for coin in coins:
        try:
            crypto_price = {
                "symbol": coin.get("coin"),
                "name": coin.get("coinName"),
                "date": datetime.now(),
                "price_usd": coin.get("regularMarketPrice"),
                "market_cap": coin.get("marketCap"),
                "volume_24h": coin.get("regularMarketVolume"),
                "change_24h": coin.get("regularMarketChangePercent"),
            }

            crypto_prices.append(crypto_price)

        except Exception as e:
            logger.error(f"Erro ao processar cripto {coin.get('coin')}: {e}")
            continue

    logger.info(f"Extraídos {len(crypto_prices)} preços de cripto")
    return crypto_prices
