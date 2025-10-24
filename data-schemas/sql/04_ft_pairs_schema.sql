-- ============================================
-- Schema Finetune - Dados para Fine-tuning
-- ============================================

-- Tabela de pares prompt/output para fine-tuning
CREATE TABLE IF NOT EXISTS finetune.ft_pairs (
    id BIGSERIAL PRIMARY KEY,
    prompt TEXT NOT NULL,
    output TEXT NOT NULL, -- JSON de ação: {"tool": "get_ohlcv", "args": {...}}
    meta JSONB, -- Metadados: tool_name, categoria, fonte, etc
    dataset VARCHAR(100), -- Nome do dataset (train, val, test)
    quality_score NUMERIC(3, 2), -- Score de qualidade (0-1, opcional)
    is_validated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_ft_pairs_dataset ON finetune.ft_pairs(dataset);
CREATE INDEX IF NOT EXISTS idx_ft_pairs_validated ON finetune.ft_pairs(is_validated);
CREATE INDEX IF NOT EXISTS idx_ft_pairs_created ON finetune.ft_pairs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ft_pairs_meta ON finetune.ft_pairs USING GIN (meta);

COMMENT ON TABLE finetune.ft_pairs IS 'Pares prompt/output para fine-tuning de tool use';
COMMENT ON COLUMN finetune.ft_pairs.output IS 'JSON com tool e args: {"tool": "get_quote", "args": {"ticker": "PETR4"}}';
COMMENT ON COLUMN finetune.ft_pairs.meta IS 'Metadados: tool_name, category, difficulty, source';

-- Tabela de métricas de avaliação
CREATE TABLE IF NOT EXISTS finetune.eval_results (
    id BIGSERIAL PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    model_version VARCHAR(100),
    eval_date TIMESTAMPTZ DEFAULT NOW(),
    dataset VARCHAR(100), -- test, golden_set, etc
    total_samples INT,
    correct_predictions INT,
    accuracy NUMERIC(5, 4), -- 0.8000 = 80%
    metrics JSONB, -- Métricas detalhadas: precision, recall, f1, confusion_matrix
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eval_results_model ON finetune.eval_results(model_name);
CREATE INDEX IF NOT EXISTS idx_eval_results_date ON finetune.eval_results(eval_date DESC);
CREATE INDEX IF NOT EXISTS idx_eval_results_accuracy ON finetune.eval_results(accuracy DESC);

COMMENT ON TABLE finetune.eval_results IS 'Resultados de avaliação de modelos fine-tunados';

-- Tabela de ferramentas (catálogo)
CREATE TABLE IF NOT EXISTS finetune.tools_catalog (
    id BIGSERIAL PRIMARY KEY,
    tool_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    category VARCHAR(50), -- quotes, historical, dividends, indicators, etc
    parameters JSONB, -- Schema dos parâmetros
    example_prompt TEXT,
    example_output TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tools_catalog_category ON finetune.tools_catalog(category);
CREATE INDEX IF NOT EXISTS idx_tools_catalog_active ON finetune.tools_catalog(is_active);

COMMENT ON TABLE finetune.tools_catalog IS 'Catálogo de ferramentas disponíveis para tool calling';

-- View para distribuição de ferramentas no dataset
CREATE OR REPLACE VIEW finetune.tool_distribution AS
SELECT
    meta->>'tool_name' as tool_name,
    dataset,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY dataset), 2) as percentage
FROM finetune.ft_pairs
WHERE meta->>'tool_name' IS NOT NULL
GROUP BY meta->>'tool_name', dataset
ORDER BY dataset, count DESC;

COMMENT ON VIEW finetune.tool_distribution IS 'Distribuição de ferramentas por dataset';

-- View para estatísticas gerais do dataset
CREATE OR REPLACE VIEW finetune.dataset_stats AS
SELECT
    dataset,
    COUNT(*) as total_pairs,
    COUNT(DISTINCT meta->>'tool_name') as unique_tools,
    COUNT(*) FILTER (WHERE is_validated = true) as validated_pairs,
    AVG(quality_score) as avg_quality_score,
    MIN(created_at) as first_created,
    MAX(created_at) as last_created
FROM finetune.ft_pairs
GROUP BY dataset
ORDER BY dataset;

COMMENT ON VIEW finetune.dataset_stats IS 'Estatísticas dos datasets de fine-tuning';

-- Função para validar distribuição balanceada
CREATE OR REPLACE FUNCTION finetune.check_balanced_distribution(
    target_dataset VARCHAR DEFAULT 'train',
    min_samples_per_tool INT DEFAULT 10,
    max_deviation_pct NUMERIC DEFAULT 30.0
)
RETURNS TABLE (
    is_balanced BOOLEAN,
    tool_name TEXT,
    sample_count BIGINT,
    expected_count NUMERIC,
    deviation_pct NUMERIC,
    status TEXT
) AS $$
DECLARE
    total_samples BIGINT;
    num_tools INT;
    expected_per_tool NUMERIC;
BEGIN
    -- Calcula total e número de ferramentas
    SELECT COUNT(*), COUNT(DISTINCT meta->>'tool_name')
    INTO total_samples, num_tools
    FROM finetune.ft_pairs
    WHERE dataset = target_dataset AND meta->>'tool_name' IS NOT NULL;

    IF num_tools = 0 THEN
        RETURN;
    END IF;

    expected_per_tool := total_samples::NUMERIC / num_tools;

    RETURN QUERY
    SELECT
        (COUNT(*) >= min_samples_per_tool
         AND ABS(COUNT(*) - expected_per_tool) / expected_per_tool * 100 <= max_deviation_pct) AS is_balanced,
        meta->>'tool_name' AS tool_name,
        COUNT(*) AS sample_count,
        expected_per_tool AS expected_count,
        ROUND(ABS(COUNT(*) - expected_per_tool) / expected_per_tool * 100, 2) AS deviation_pct,
        CASE
            WHEN COUNT(*) < min_samples_per_tool THEN 'insuficiente'
            WHEN ABS(COUNT(*) - expected_per_tool) / expected_per_tool * 100 > max_deviation_pct THEN 'desbalanceado'
            ELSE 'ok'
        END AS status
    FROM finetune.ft_pairs
    WHERE dataset = target_dataset AND meta->>'tool_name' IS NOT NULL
    GROUP BY meta->>'tool_name'
    ORDER BY sample_count DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION finetune.check_balanced_distribution IS 'Verifica se dataset está balanceado entre ferramentas';

-- Função para atualizar updated_at
CREATE OR REPLACE FUNCTION finetune.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers
CREATE TRIGGER update_ft_pairs_updated_at BEFORE UPDATE ON finetune.ft_pairs
    FOR EACH ROW EXECUTE FUNCTION finetune.update_updated_at_column();

CREATE TRIGGER update_tools_catalog_updated_at BEFORE UPDATE ON finetune.tools_catalog
    FOR EACH ROW EXECUTE FUNCTION finetune.update_updated_at_column();

-- Grants (opcional)
-- GRANT USAGE ON SCHEMA finetune TO llmops_user;
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA finetune TO llmops_user;
-- GRANT SELECT ON ALL VIEWS IN SCHEMA finetune TO llmops_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA finetune TO llmops_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA finetune TO llmops_user;




