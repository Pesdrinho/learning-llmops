-- ============================================
-- Schema Agents - Análises Geradas por Agentes
-- ============================================

-- Adiciona coluna architecture na tabela de logs (se não existir)
ALTER TABLE observability.llm_logs
ADD COLUMN IF NOT EXISTS architecture VARCHAR(50);

CREATE INDEX IF NOT EXISTS idx_llm_logs_architecture
ON observability.llm_logs(architecture);

COMMENT ON COLUMN observability.llm_logs.architecture IS 'Arquitetura que gerou o log (agents, rag, api-blackbox, etc)';

-- Schema para análises geradas
CREATE SCHEMA IF NOT EXISTS analysis;

-- Tabela de relatórios gerados
CREATE TABLE IF NOT EXISTS analysis.generated_reports (
    id BIGSERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    analysis_type VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    cost_usd NUMERIC(10, 6),
    tools_used TEXT[],
    request_id VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para melhor performance
CREATE INDEX IF NOT EXISTS idx_reports_ticker ON analysis.generated_reports(ticker);
CREATE INDEX IF NOT EXISTS idx_reports_type ON analysis.generated_reports(analysis_type);
CREATE INDEX IF NOT EXISTS idx_reports_created ON analysis.generated_reports(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_request_id ON analysis.generated_reports(request_id);

COMMENT ON TABLE analysis.generated_reports IS 'Análises de ações geradas por agentes';
COMMENT ON COLUMN analysis.generated_reports.ticker IS 'Código da ação (ex: PETR4, VALE3)';
COMMENT ON COLUMN analysis.generated_reports.analysis_type IS 'Tipo de análise (price_movement, volume_analysis, etc)';
COMMENT ON COLUMN analysis.generated_reports.content IS 'Conteúdo da análise em formato markdown';
COMMENT ON COLUMN analysis.generated_reports.metadata IS 'Metadados adicionais (period_days, etc)';
COMMENT ON COLUMN analysis.generated_reports.tools_used IS 'Ferramentas utilizadas na análise (nl2sql, websearch)';

-- Função para atualizar updated_at
CREATE OR REPLACE FUNCTION analysis.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger para atualizar updated_at
DROP TRIGGER IF EXISTS update_reports_updated_at ON analysis.generated_reports;
CREATE TRIGGER update_reports_updated_at
    BEFORE UPDATE ON analysis.generated_reports
    FOR EACH ROW EXECUTE FUNCTION analysis.update_updated_at_column();

-- View para últimas análises por ticker
CREATE OR REPLACE VIEW analysis.latest_reports_by_ticker AS
SELECT DISTINCT ON (ticker)
    id,
    ticker,
    analysis_type,
    content,
    metadata,
    cost_usd,
    tools_used,
    request_id,
    created_at
FROM analysis.generated_reports
ORDER BY ticker, created_at DESC;

COMMENT ON VIEW analysis.latest_reports_by_ticker IS 'Última análise de cada ticker';

-- View para estatísticas de análises
CREATE OR REPLACE VIEW analysis.report_stats AS
SELECT
    analysis_type,
    COUNT(*) as total_reports,
    COUNT(DISTINCT ticker) as unique_tickers,
    AVG(cost_usd) as avg_cost_usd,
    SUM(cost_usd) as total_cost_usd,
    MIN(created_at) as first_report,
    MAX(created_at) as last_report
FROM analysis.generated_reports
GROUP BY analysis_type
ORDER BY total_reports DESC;

COMMENT ON VIEW analysis.report_stats IS 'Estatísticas de análises geradas';

-- Grants (opcional, ajuste conforme necessário)
-- GRANT USAGE ON SCHEMA analysis TO llmops_user;
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA analysis TO llmops_user;
-- GRANT SELECT ON ALL VIEWS IN SCHEMA analysis TO llmops_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA analysis TO llmops_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA analysis TO llmops_user;
