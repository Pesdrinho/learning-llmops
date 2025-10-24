"""Extractor de dados de inflação (IPCA) e SELIC"""

from datetime import datetime
from typing import Any

from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


async def extract_inflation(data: dict[str, Any]) -> list[dict]:
    """
    Extrai dados de inflação (IPCA) da resposta da API

    Args:
        data: Resposta da API Brapi

    Returns:
        Lista de dados de inflação
    """
    inflation_data = data.get("inflation", [])
    inflation_records = []

    for item in inflation_data:
        try:
            # Converte data no formato DD/MM/YYYY
            date_str = item.get("date")
            date = datetime.strptime(date_str, "%d/%m/%Y").date()

            inflation_record = {
                "date": date,
                "value": item.get("value"),
                "accumulated_12m": item.get("epochValue12Months"),
            }

            inflation_records.append(inflation_record)

        except Exception as e:
            logger.error(f"Erro ao processar inflação: {e}")
            continue

    logger.info(f"Extraídos {len(inflation_records)} registros de inflação")
    return inflation_records


async def extract_selic(data: dict[str, Any]) -> list[dict]:
    """
    Extrai dados da taxa SELIC da resposta da API

    Args:
        data: Resposta da API Brapi

    Returns:
        Lista de dados da SELIC
    """
    selic_data = data.get("primeRate", [])
    selic_records = []

    for item in selic_data:
        try:
            # Converte data no formato DD/MM/YYYY
            date_str = item.get("date")
            date = datetime.strptime(date_str, "%d/%m/%Y").date()

            selic_record = {
                "date": date,
                "rate": item.get("value"),
            }

            selic_records.append(selic_record)

        except Exception as e:
            logger.error(f"Erro ao processar SELIC: {e}")
            continue

    logger.info(f"Extraídos {len(selic_records)} registros de SELIC")
    return selic_records




