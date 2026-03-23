"""
Orquestrador principal do Crawler Brapi
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from brapi_client import get_brapi_client
from extractors import (
    crypto,
    dividends,
    fx_rates,
    inflation,
    ohlcv,
    quotes,
)
from loaders import (
    upsert_assets,
    upsert_crypto,
    upsert_dividends,
    upsert_fx_rates,
    upsert_inflation,
    upsert_ohlcv,
    upsert_selic,
)

from llmops_lab.db.connectors import get_async_db
from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


async def crawl_quotes(client, db, tickers: list[str]):
    """Coleta cotações"""
    logger.info(f"Coletando cotações de {len(tickers)} tickers")

    try:
        # Plano gratuito: 1 ticker por requisição
        for ticker in tickers:
            try:
                data = await client.get_quote([ticker])

                # Extrai e salva
                quote_data = await quotes.extract_quotes(data)
                if quote_data:
                    assets = [q["asset"] for q in quote_data]
                    quote_records = [q["quote"] for q in quote_data]

                    await upsert_assets(db, assets)
                    await upsert_ohlcv(db, quote_records)

                    logger.info(f"Cotação de {ticker} coletada com sucesso")
                else:
                    logger.warning(f"Nenhum dado de cotação para {ticker}")

                # Delay para respeitar rate limits
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Erro ao coletar cotação de {ticker}: {e}")
                continue

        logger.info("Coleta de cotações completa")

    except Exception as e:
        logger.error(f"Erro ao coletar cotações: {e}")


async def crawl_historical(client, db, ticker: str, range: str = "1mo"):
    """Coleta dados históricos de um ticker"""
    logger.info(f"Coletando histórico de {ticker}")

    try:
        data = await client.get_historical_data(ticker=ticker, range=range, dividends=True)

        # Extrai OHLCV
        ohlcv_data = await ohlcv.extract_ohlcv(data)
        await upsert_ohlcv(db, ohlcv_data)

        # Extrai dividendos
        div_data = await dividends.extract_dividends(data)
        await upsert_dividends(db, div_data)

    except Exception as e:
        logger.error(f"Erro ao coletar histórico de {ticker}: {e}")


async def crawl_fx_rates(client, db):
    """Coleta taxas de câmbio"""
    logger.info("Coletando taxas de câmbio")

    try:
        # Principais pares
        pairs = ["USD-BRL", "EUR-BRL", "GBP-BRL", "BTC-BRL", "EUR-USD"]

        for pair in pairs:
            data = await client.get_currency(pair)
            fx_data = await fx_rates.extract_fx_rates(data)
            await upsert_fx_rates(db, fx_data)
            await asyncio.sleep(1)  # Rate limiting para FX

        logger.info("Coleta de FX rates completa")

    except Exception as e:
        logger.error(f"Erro ao coletar FX rates: {e}")


async def crawl_crypto(client, db):
    """Coleta preços de criptomoedas"""
    logger.info("Coletando preços de criptomoedas")

    try:
        data = await client.get_crypto()
        crypto_data = await crypto.extract_crypto(data)
        await upsert_crypto(db, crypto_data)

        # Delay após coleta de crypto
        await asyncio.sleep(1)

        logger.info("Coleta de cripto completa")

    except Exception as e:
        logger.error(f"Erro ao coletar cripto: {e}")


async def crawl_inflation(client, db):
    """Coleta dados de inflação (IPCA)"""
    logger.info("Coletando dados de inflação")

    try:
        # Últimos 12 meses
        end_date = datetime.now().strftime("%d/%m/%Y")
        start_date = (datetime.now() - timedelta(days=365)).strftime("%d/%m/%Y")

        data = await client.get_inflation(start=start_date, end=end_date)

        inflation_data = await inflation.extract_inflation(data)
        await upsert_inflation(db, inflation_data)

        # Delay após coleta de inflação
        await asyncio.sleep(1)

        logger.info("Coleta de inflação completa")

    except Exception as e:
        logger.error(f"Erro ao coletar inflação: {e}")


async def crawl_selic(client, db):
    """Coleta dados da taxa SELIC"""
    logger.info("Coletando dados da SELIC")

    try:
        # Últimos 12 meses
        end_date = datetime.now().strftime("%d/%m/%Y")
        start_date = (datetime.now() - timedelta(days=365)).strftime("%d/%m/%Y")

        data = await client.get_prime_rate(start=start_date, end=end_date)

        selic_data = await inflation.extract_selic(data)
        await upsert_selic(db, selic_data)

        # Delay após coleta de SELIC
        await asyncio.sleep(1)

        logger.info("Coleta de SELIC completa")

    except Exception as e:
        logger.error(f"Erro ao coletar SELIC: {e}")


async def run_full_crawl(sample: bool = False):
    """
    Executa crawler completo

    Args:
        sample: Se True, coleta apenas uma amostra pequena (para testes)
    """
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info("Iniciando Crawler Brapi")
    logger.info(f"Modo: {'SAMPLE' if sample else 'FULL'}")
    logger.info("=" * 80)

    # Conecta ao banco
    db = get_async_db()
    await db.connect()

    # Conecta ao cliente Brapi
    async with await get_brapi_client() as client:
        # Health check
        is_healthy = await client.health_check()
        if not is_healthy:
            logger.error("Brapi API não está respondendo. Abortando.")
            return

        try:
            # 1. Coleta lista de tickers disponíveis
            logger.info("Obtendo lista de tickers...")

            # Tickers principais como fallback
            fallback_tickers = [
                "PETR4",
                "VALE3",
                "ITUB4",
                "BBDC4",
                "MGLU3",
                "ABEV3",
                "WEGE3",
                "B3SA3",
                "RENT3",
                "SUZB3",
                "RAIL3",
                "JBSS3",
                "EMBR3",
                "TOTS3",
                "RDOR3",
                "GGBR4",
                "USIM5",
                "CSAN3",
                "BBAS3",
                "ELET3",
            ]

            try:
                available_data = await client.get_available_tickers(limit=1000)

                # Validação defensiva da resposta
                if not isinstance(available_data, dict):
                    logger.error(
                        f"Resposta inválida da API (tipo {type(available_data).__name__}). "
                        f"Usando tickers fallback. Resposta: {str(available_data)[:200]}"
                    )
                    all_tickers = fallback_tickers
                elif "stocks" not in available_data:
                    logger.warning(
                        f"Resposta sem campo 'stocks'. Usando tickers fallback. "
                        f"Chaves disponíveis: {list(available_data.keys())}"
                    )
                    all_tickers = fallback_tickers
                else:
                    stocks_list = available_data.get("stocks", [])
                    if not isinstance(stocks_list, list):
                        logger.error(
                            f"Campo 'stocks' não é uma lista (tipo {type(stocks_list).__name__}). "
                            f"Usando tickers fallback."
                        )
                        all_tickers = fallback_tickers
                    else:
                        all_tickers = [
                            stock["stock"]
                            for stock in stocks_list
                            if isinstance(stock, dict) and "stock" in stock
                        ]

                        if not all_tickers:
                            logger.warning(
                                "Nenhum ticker válido encontrado. Usando tickers fallback."
                            )
                            all_tickers = fallback_tickers
                        else:
                            logger.info(f"Sucesso! {len(all_tickers)} tickers obtidos da API")

            except Exception as e:
                logger.error(f"Erro ao obter tickers da API: {e}. Usando tickers fallback.")
                all_tickers = fallback_tickers

            if sample:
                # Amostra: apenas alguns tickers principais
                tickers = fallback_tickers[:5]
            else:
                tickers = all_tickers

            logger.info(f"Total de tickers para processar: {len(tickers)}")

            # 2. Coleta cotações atuais
            await crawl_quotes(client, db, tickers)

            # 3. Coleta histórico (apenas para amostra de tickers)
            if sample:
                sample_tickers = tickers[:3]
            else:
                # Em produção, escolhe top 50 por volume
                sample_tickers = tickers[:50]

            for ticker in sample_tickers:
                await crawl_historical(client, db, ticker, range="3mo" if sample else "1y")
                await asyncio.sleep(2)  # Rate limiting - delay maior para histórico

            # 4. Coleta taxas de câmbio
            await crawl_fx_rates(client, db)

            # 5. Coleta criptomoedas
            await crawl_crypto(client, db)

            # 6. Coleta inflação
            await crawl_inflation(client, db)

            # 7. Coleta SELIC
            await crawl_selic(client, db)

        except Exception as e:
            logger.error(f"Erro durante execução do crawler: {e}")
            raise
        finally:
            await db.disconnect()

    # Resumo
    duration = (datetime.now() - start_time).total_seconds()
    logger.info("=" * 80)
    logger.info(f"Crawler finalizado em {duration:.2f} segundos")
    logger.info("=" * 80)


async def main():
    """Entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Crawler Brapi")
    parser.add_argument(
        "--sample", action="store_true", help="Executa em modo sample (poucos dados para teste)"
    )

    args = parser.parse_args()

    await run_full_crawl(sample=args.sample)


if __name__ == "__main__":
    asyncio.run(main())
