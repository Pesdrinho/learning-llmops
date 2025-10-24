"""Extractor de dados históricos OHLCV"""

from datetime import datetime
from typing import Any

from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


async def extract_ohlcv(data: dict[str, Any]) -> list[dict]:
    """
    Extrai dados históricos OHLCV da resposta da API

    Args:
        data: Resposta da API Brapi

    Returns:
        Lista de registros OHLCV
    """
    results = data.get("results", [])
    ohlcv_records = []

    for result in results:
        ticker = result.get("symbol")
        historical_data = result.get("historicalDataPrice", [])

        for price_data in historical_data:
            try:
                # Converte timestamp para date
                date = datetime.fromtimestamp(price_data.get("date")).date()

                ohlcv = {
                    "ticker": ticker,
                    "date": date,
                    "open": price_data.get("open"),
                    "high": price_data.get("high"),
                    "low": price_data.get("low"),
                    "close": price_data.get("close"),
                    "volume": price_data.get("volume"),
                    "adjusted_close": price_data.get("adjustedClose") or price_data.get("close"),
                }

                ohlcv_records.append(ohlcv)

            except Exception as e:
                logger.error(f"Erro ao processar OHLCV {ticker}: {e}")
                continue

    logger.info(f"Extraídos {len(ohlcv_records)} registros OHLCV")
    return ohlcv_records




