#!/usr/bin/env python3
"""
Script para ingestão de amostra de dados da Brapi
"""

import asyncio
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


async def main():
    """Executa ingestão de amostra"""
    logger.info("=" * 80)
    logger.info("Ingestão de Amostra - Brapi API")
    logger.info("=" * 80)

    # Import do crawler
    from pipelines.crawler_brapi.app.main import run_full_crawl

    # Executa crawler em modo sample
    await run_full_crawl(sample=True)

    logger.info("Ingestão de amostra completa!")
    logger.info("Verifique os dados com: psql -d llmops -c 'SELECT COUNT(*) FROM market.assets;'")


if __name__ == "__main__":
    asyncio.run(main())




