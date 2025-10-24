"""
Loaders para inserir/upsert dados no Cloud SQL
"""


from llmops_lab.db.connectors import AsyncDatabaseConnection
from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


async def upsert_assets(db: AsyncDatabaseConnection, assets: list[dict]):
    """
    Insere ou atualiza assets no banco

    Args:
        db: Conexão com banco
        assets: Lista de assets
    """
    if not assets:
        return

    query = """
        INSERT INTO market.assets (ticker, name, sector, industry, asset_type, currency, metadata, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
        ON CONFLICT (ticker) DO UPDATE SET
            name = EXCLUDED.name,
            sector = EXCLUDED.sector,
            industry = EXCLUDED.industry,
            asset_type = EXCLUDED.asset_type,
            currency = EXCLUDED.currency,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
    """

    async with db.pool.acquire() as conn:
        for asset in assets:
            try:
                await conn.execute(
                    query,
                    asset["ticker"],
                    asset.get("name"),
                    asset.get("sector"),
                    asset.get("industry"),
                    asset.get("asset_type"),
                    asset.get("currency"),
                    asset.get("metadata"),
                )
            except Exception as e:
                logger.error(f"Erro ao inserir asset {asset['ticker']}: {e}")

    logger.info(f"Upsert de {len(assets)} assets completo")


async def upsert_ohlcv(db: AsyncDatabaseConnection, ohlcv_records: list[dict]):
    """
    Insere ou atualiza dados OHLCV no banco

    Args:
        db: Conexão com banco
        ohlcv_records: Lista de registros OHLCV
    """
    if not ohlcv_records:
        return

    query = """
        INSERT INTO market.ohlcv (ticker, date, open, high, low, close, volume, adjusted_close)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (ticker, date) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            adjusted_close = EXCLUDED.adjusted_close
    """

    async with db.pool.acquire() as conn:
        for record in ohlcv_records:
            try:
                await conn.execute(
                    query,
                    record["ticker"],
                    record["date"],
                    record.get("open"),
                    record.get("high"),
                    record.get("low"),
                    record.get("close"),
                    record.get("volume"),
                    record.get("adjusted_close"),
                )
            except Exception as e:
                logger.error(f"Erro ao inserir OHLCV {record['ticker']} {record['date']}: {e}")

    logger.info(f"Upsert de {len(ohlcv_records)} registros OHLCV completo")


async def upsert_dividends(db: AsyncDatabaseConnection, dividends: list[dict]):
    """
    Insere ou atualiza dividendos no banco

    Args:
        db: Conexão com banco
        dividends: Lista de dividendos
    """
    if not dividends:
        return

    query = """
        INSERT INTO market.dividends (ticker, date, type, value, currency, payment_date)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (ticker, date, type) DO UPDATE SET
            value = EXCLUDED.value,
            currency = EXCLUDED.currency,
            payment_date = EXCLUDED.payment_date
    """

    async with db.pool.acquire() as conn:
        for dividend in dividends:
            try:
                await conn.execute(
                    query,
                    dividend["ticker"],
                    dividend["date"],
                    dividend.get("type"),
                    dividend.get("value"),
                    dividend.get("currency"),
                    dividend.get("payment_date"),
                )
            except Exception as e:
                logger.error(f"Erro ao inserir dividend {dividend['ticker']}: {e}")

    logger.info(f"Upsert de {len(dividends)} dividendos completo")


async def upsert_fx_rates(db: AsyncDatabaseConnection, fx_rates: list[dict]):
    """
    Insere ou atualiza taxas de câmbio no banco

    Args:
        db: Conexão com banco
        fx_rates: Lista de taxas de câmbio
    """
    if not fx_rates:
        return

    query = """
        INSERT INTO market.fx_rates (base_currency, quote_currency, date, rate)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (base_currency, quote_currency, date) DO UPDATE SET
            rate = EXCLUDED.rate
    """

    async with db.pool.acquire() as conn:
        for fx_rate in fx_rates:
            try:
                await conn.execute(
                    query,
                    fx_rate["base_currency"],
                    fx_rate["quote_currency"],
                    fx_rate["date"],
                    fx_rate.get("rate"),
                )
            except Exception as e:
                logger.error(f"Erro ao inserir FX rate: {e}")

    logger.info(f"Upsert de {len(fx_rates)} taxas de câmbio completo")


async def upsert_crypto(db: AsyncDatabaseConnection, crypto_prices: list[dict]):
    """
    Insere ou atualiza preços de criptomoedas no banco

    Args:
        db: Conexão com banco
        crypto_prices: Lista de preços de cripto
    """
    if not crypto_prices:
        return

    query = """
        INSERT INTO market.crypto_prices (symbol, name, date, price_usd, market_cap, volume_24h, change_24h)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (symbol, date) DO UPDATE SET
            name = EXCLUDED.name,
            price_usd = EXCLUDED.price_usd,
            market_cap = EXCLUDED.market_cap,
            volume_24h = EXCLUDED.volume_24h,
            change_24h = EXCLUDED.change_24h
    """

    async with db.pool.acquire() as conn:
        for crypto in crypto_prices:
            try:
                await conn.execute(
                    query,
                    crypto["symbol"],
                    crypto.get("name"),
                    crypto["date"],
                    crypto.get("price_usd"),
                    crypto.get("market_cap"),
                    crypto.get("volume_24h"),
                    crypto.get("change_24h"),
                )
            except Exception as e:
                logger.error(f"Erro ao inserir crypto {crypto['symbol']}: {e}")

    logger.info(f"Upsert de {len(crypto_prices)} preços de cripto completo")


async def upsert_inflation(db: AsyncDatabaseConnection, inflation_records: list[dict]):
    """
    Insere ou atualiza dados de inflação no banco

    Args:
        db: Conexão com banco
        inflation_records: Lista de dados de inflação
    """
    if not inflation_records:
        return

    query = """
        INSERT INTO market.inflation_ipca (date, value, accumulated_12m)
        VALUES ($1, $2, $3)
        ON CONFLICT (date) DO UPDATE SET
            value = EXCLUDED.value,
            accumulated_12m = EXCLUDED.accumulated_12m
    """

    async with db.pool.acquire() as conn:
        for record in inflation_records:
            try:
                await conn.execute(
                    query,
                    record["date"],
                    record.get("value"),
                    record.get("accumulated_12m"),
                )
            except Exception as e:
                logger.error(f"Erro ao inserir inflação: {e}")

    logger.info(f"Upsert de {len(inflation_records)} registros de inflação completo")


async def upsert_selic(db: AsyncDatabaseConnection, selic_records: list[dict]):
    """
    Insere ou atualiza dados da SELIC no banco

    Args:
        db: Conexão com banco
        selic_records: Lista de dados da SELIC
    """
    if not selic_records:
        return

    query = """
        INSERT INTO market.selic (date, rate)
        VALUES ($1, $2)
        ON CONFLICT (date) DO UPDATE SET
            rate = EXCLUDED.rate
    """

    async with db.pool.acquire() as conn:
        for record in selic_records:
            try:
                await conn.execute(
                    query,
                    record["date"],
                    record.get("rate"),
                )
            except Exception as e:
                logger.error(f"Erro ao inserir SELIC: {e}")

    logger.info(f"Upsert de {len(selic_records)} registros de SELIC completo")




