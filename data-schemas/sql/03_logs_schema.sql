-- ============================================
-- Schema Observability - Logs e Métricas
-- ============================================

-- Tabela de logs de LLM
CREATE TABLE IF NOT EXISTS observability.llm_logs (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ DEFAULT NOW(),
    user_id TEXT,
    model TEXT NOT NULL,
    provider TEXT,
    prompt_masked TEXT, -- Prompt com PII mascarado
    response_masked TEXT, -- Resposta com PII mascarado
    input_tokens INT,
    output_tokens INT,
    cost_usd NUMERIC(10, 6),
    latency_ms INT,
    status VARCHAR(50) DEFAULT 'success', -- success, error, rate_limited
    error_message TEXT,
    metadata JSONB, -- Metadados adicionais (tags, contexto, etc)
    inference_type VARCHAR(50), -- chat_completion, dataset_generation
    guardrails_triggered TEXT[], -- Lista de guardrails que foram acionados
    prompt_version VARCHAR(20), -- Versão do prompt template usado
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_llm_logs_ts ON observability.llm_logs(ts DESC);
CREATE INDEX IF NOT EXISTS idx_llm_logs_model ON observability.llm_logs(model);
CREATE INDEX IF NOT EXISTS idx_llm_logs_user ON observability.llm_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_llm_logs_status ON observability.llm_logs(status);
CREATE INDEX IF NOT EXISTS idx_llm_logs_inference_type ON observability.llm_logs(inference_type);
CREATE INDEX IF NOT EXISTS idx_llm_logs_prompt_version ON observability.llm_logs(prompt_version);
-- CREATE INDEX IF NOT EXISTS idx_llm_logs_date ON observability.llm_logs(DATE(ts));

COMMENT ON TABLE observability.llm_logs IS 'Logs detalhados de chamadas LLM';
COMMENT ON COLUMN observability.llm_logs.prompt_masked IS 'Prompt com PII removido';
COMMENT ON COLUMN observability.llm_logs.response_masked IS 'Resposta com PII removido';
COMMENT ON COLUMN observability.llm_logs.inference_type IS 'Tipo de inferência (chat_completion, dataset_generation)';
COMMENT ON COLUMN observability.llm_logs.guardrails_triggered IS 'Lista de guardrails acionados durante a requisição';
COMMENT ON COLUMN observability.llm_logs.prompt_version IS 'Versão do prompt template utilizado';

-- Tabela de controle de gastos (ledger)
CREATE TABLE IF NOT EXISTS observability.spend_ledger (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ DEFAULT NOW(),
    api_key_hash VARCHAR(64), -- SHA256 da API key para tracking
    model TEXT NOT NULL,
    cost_usd NUMERIC(10, 6) NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_spend_ledger_ts ON observability.spend_ledger(ts DESC);
-- CREATE INDEX IF NOT EXISTS idx_spend_ledger_date ON observability.spend_ledger(DATE(ts));
CREATE INDEX IF NOT EXISTS idx_spend_ledger_api_key ON observability.spend_ledger(api_key_hash);
CREATE INDEX IF NOT EXISTS idx_spend_ledger_model ON observability.spend_ledger(model);

COMMENT ON TABLE observability.spend_ledger IS 'Ledger de gastos para rate limiting';

-- View para custos diários
CREATE OR REPLACE VIEW observability.daily_costs AS
SELECT
    DATE(ts) as date,
    COUNT(*) as total_requests,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(cost_usd) as total_cost_usd,
    AVG(latency_ms) as avg_latency_ms,
    COUNT(DISTINCT user_id) as unique_users
FROM observability.llm_logs
GROUP BY DATE(ts)
ORDER BY DATE(ts) DESC;

COMMENT ON VIEW observability.daily_costs IS 'Resumo de custos por dia';

-- View para custos por modelo
CREATE OR REPLACE VIEW observability.costs_by_model AS
SELECT
    model,
    COUNT(*) as total_requests,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(cost_usd) as total_cost_usd,
    AVG(latency_ms) as avg_latency_ms,
    AVG(cost_usd) as avg_cost_per_request
FROM observability.llm_logs
GROUP BY model
ORDER BY total_cost_usd DESC;

COMMENT ON VIEW observability.costs_by_model IS 'Custos agrupados por modelo';

-- Tabela de eventos de sistema
CREATE TABLE IF NOT EXISTS observability.system_events (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ DEFAULT NOW(),
    event_type VARCHAR(100) NOT NULL, -- crawler_run, rag_ingest, agent_execution, etc
    component VARCHAR(100), -- crawler, rag, agents, api
    status VARCHAR(50), -- started, completed, failed
    duration_ms INT,
    details JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_system_events_ts ON observability.system_events(ts DESC);
CREATE INDEX IF NOT EXISTS idx_system_events_type ON observability.system_events(event_type);
CREATE INDEX IF NOT EXISTS idx_system_events_component ON observability.system_events(component);
CREATE INDEX IF NOT EXISTS idx_system_events_status ON observability.system_events(status);

COMMENT ON TABLE observability.system_events IS 'Eventos de sistema e pipelines';

-- Função para obter gastos do dia
CREATE OR REPLACE FUNCTION observability.get_daily_spend(
    target_date DATE DEFAULT CURRENT_DATE,
    api_key_hash_filter TEXT DEFAULT NULL
)
RETURNS NUMERIC AS $$
DECLARE
    total_spent NUMERIC;
BEGIN
    SELECT COALESCE(SUM(cost_usd), 0)
    INTO total_spent
    FROM observability.spend_ledger
    WHERE DATE(ts) = target_date
        AND (api_key_hash_filter IS NULL OR api_key_hash = api_key_hash_filter);

    RETURN total_spent;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION observability.get_daily_spend IS 'Retorna gasto total de um dia';

-- Função para verificar se atingiu limite diário
CREATE OR REPLACE FUNCTION observability.check_daily_limit(
    daily_limit_usd NUMERIC,
    api_key_hash_filter TEXT DEFAULT NULL
)
RETURNS TABLE (
    allowed BOOLEAN,
    spent_today NUMERIC,
    limit_usd NUMERIC,
    remaining_usd NUMERIC,
    usage_pct NUMERIC
) AS $$
DECLARE
    spent NUMERIC;
BEGIN
    spent := observability.get_daily_spend(CURRENT_DATE, api_key_hash_filter);

    RETURN QUERY SELECT
        spent < daily_limit_usd AS allowed,
        spent AS spent_today,
        daily_limit_usd AS limit_usd,
        daily_limit_usd - spent AS remaining_usd,
        ROUND((spent / NULLIF(daily_limit_usd, 0) * 100)::NUMERIC, 2) AS usage_pct;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION observability.check_daily_limit IS 'Verifica se atingiu limite diário de gastos';

-- Grants (opcional)
-- GRANT USAGE ON SCHEMA observability TO llmops_user;
-- GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA observability TO llmops_user;
-- GRANT SELECT ON ALL VIEWS IN SCHEMA observability TO llmops_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA observability TO llmops_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA observability TO llmops_user;
