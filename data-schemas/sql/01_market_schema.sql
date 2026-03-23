-- ============================================
-- Schema Market - Dados Brapi API
-- ============================================

-- Tabela de ativos (ações, fiis, etc)
CREATE TABLE IF NOT EXISTS market.assets (
    id BIGSERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(255),
    sector VARCHAR(100),
    industry VARCHAR(100),
    asset_type VARCHAR(50), -- stock, fii, etf, etc
    currency VARCHAR(10) DEFAULT 'BRL',
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assets_ticker ON market.assets(ticker);
CREATE INDEX IF NOT EXISTS idx_assets_sector ON market.assets(sector);
CREATE INDEX IF NOT EXISTS idx_assets_type ON market.assets(asset_type);

COMMENT ON TABLE market.assets IS 'Ativos financeiros (ações, FIIs, ETFs)';

-- Tabela OHLCV (preços históricos)
CREATE TABLE IF NOT EXISTS market.ohlcv (
    id BIGSERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    open NUMERIC(15, 2),
    high NUMERIC(15, 2),
    low NUMERIC(15, 2),
    close NUMERIC(15, 2),
    volume BIGINT,
    adjusted_close NUMERIC(15, 2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_ohlcv_ticker_date ON market.ohlcv(ticker, date DESC);
CREATE INDEX IF NOT EXISTS idx_ohlcv_date ON market.ohlcv(date DESC);

COMMENT ON TABLE market.ohlcv IS 'Dados históricos OHLC + Volume';

-- Tabela de dividendos
CREATE TABLE IF NOT EXISTS market.dividends (
    id BIGSERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    type VARCHAR(50), -- dividendo, jcp, etc
    value NUMERIC(10, 4),
    currency VARCHAR(10) DEFAULT 'BRL',
    payment_date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(ticker, date, type)
);

CREATE INDEX IF NOT EXISTS idx_dividends_ticker_date ON market.dividends(ticker, date DESC);

COMMENT ON TABLE market.dividends IS 'Dividendos e proventos';

-- Tabela de taxas de câmbio
CREATE TABLE IF NOT EXISTS market.fx_rates (
    id BIGSERIAL PRIMARY KEY,
    base_currency VARCHAR(10) NOT NULL,
    quote_currency VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    rate NUMERIC(15, 6),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(base_currency, quote_currency, date)
);

CREATE INDEX IF NOT EXISTS idx_fx_rates_pair_date ON market.fx_rates(base_currency, quote_currency, date DESC);

COMMENT ON TABLE market.fx_rates IS 'Taxas de câmbio';

-- Tabela de criptomoedas
CREATE TABLE IF NOT EXISTS market.crypto_prices (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    date TIMESTAMPTZ NOT NULL,
    price_usd NUMERIC(18, 8),
    market_cap NUMERIC(20, 2),
    volume_24h NUMERIC(20, 2),
    change_24h NUMERIC(10, 4),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, date)
);

CREATE INDEX IF NOT EXISTS idx_crypto_symbol_date ON market.crypto_prices(symbol, date DESC);

COMMENT ON TABLE market.crypto_prices IS 'Preços de criptomoedas';

-- Tabela SELIC
CREATE TABLE IF NOT EXISTS market.selic (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    rate NUMERIC(6, 4),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_selic_date ON market.selic(date DESC);

COMMENT ON TABLE market.selic IS 'Taxa SELIC histórica';

-- Tabela IPCA (inflação)
CREATE TABLE IF NOT EXISTS market.inflation_ipca (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    value NUMERIC(6, 4), -- Variação percentual
    accumulated_12m NUMERIC(6, 4),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ipca_date ON market.inflation_ipca(date DESC);

COMMENT ON TABLE market.inflation_ipca IS 'Índice IPCA de inflação';

-- Função para atualizar updated_at
CREATE OR REPLACE FUNCTION market.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger para atualizar updated_at em assets
DROP TRIGGER IF EXISTS update_assets_updated_at ON market.assets;
CREATE TRIGGER update_assets_updated_at BEFORE UPDATE ON market.assets
    FOR EACH ROW EXECUTE FUNCTION market.update_updated_at_column();

-- Grants (opcional, ajuste conforme necessário)
-- GRANT USAGE ON SCHEMA market TO llmops_user;
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA market TO llmops_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA market TO llmops_user;
