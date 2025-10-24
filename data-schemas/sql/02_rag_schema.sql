-- ============================================
-- Schema RAG - Documentos e Embeddings
-- ============================================

-- Tabela de chunks de documentos com embeddings
CREATE TABLE IF NOT EXISTS rag.doc_chunks (
    id BIGSERIAL PRIMARY KEY,
    source_id TEXT NOT NULL, -- Identificador do documento original
    source_type VARCHAR(50), -- pdf, markdown, html, etc
    source_url TEXT, -- URL ou caminho do documento original
    content TEXT NOT NULL, -- Texto do chunk
    chunk_index INT, -- Índice do chunk no documento
    metadata JSONB, -- Metadados flexíveis (ticker, data, setor, etc)
    embedding VECTOR(1536), -- Embedding OpenAI text-embedding-3-small
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_doc_chunks_source ON rag.doc_chunks(source_id);
CREATE INDEX IF NOT EXISTS idx_doc_chunks_type ON rag.doc_chunks(source_type);
CREATE INDEX IF NOT EXISTS idx_doc_chunks_created ON rag.doc_chunks(created_at DESC);

-- Índice IVFFLAT para busca vetorial (ajuste lists conforme volume de dados)
-- lists = sqrt(total_rows) é uma boa heurística inicial
-- Para 10k rows: lists = 100; Para 100k rows: lists = 316; Para 1M rows: lists = 1000
CREATE INDEX IF NOT EXISTS idx_doc_chunks_embedding 
ON rag.doc_chunks 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);

-- Índice GIN para busca em metadata JSONB
CREATE INDEX IF NOT EXISTS idx_doc_chunks_metadata ON rag.doc_chunks USING GIN (metadata);

COMMENT ON TABLE rag.doc_chunks IS 'Chunks de documentos com embeddings para RAG';
COMMENT ON COLUMN rag.doc_chunks.embedding IS 'Embedding OpenAI 1536 dims';
COMMENT ON COLUMN rag.doc_chunks.metadata IS 'Metadados: ticker, date, report_type, etc';

-- Tabela de documentos originais (tracking)
CREATE TABLE IF NOT EXISTS rag.documents (
    id BIGSERIAL PRIMARY KEY,
    source_id TEXT NOT NULL UNIQUE,
    source_type VARCHAR(50),
    title TEXT,
    url TEXT,
    content_hash VARCHAR(64), -- SHA256 do conteúdo
    total_chunks INT,
    metadata JSONB,
    status VARCHAR(50) DEFAULT 'pending', -- pending, processed, failed
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_documents_source_id ON rag.documents(source_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON rag.documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_created ON rag.documents(created_at DESC);

COMMENT ON TABLE rag.documents IS 'Tracking de documentos originais';

-- Função para busca de similaridade (helper)
CREATE OR REPLACE FUNCTION rag.search_similar_chunks(
    query_embedding VECTOR(1536),
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 5,
    filter_metadata JSONB DEFAULT NULL
)
RETURNS TABLE (
    id BIGINT,
    source_id TEXT,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id,
        dc.source_id,
        dc.content,
        dc.metadata,
        1 - (dc.embedding <=> query_embedding) AS similarity
    FROM rag.doc_chunks dc
    WHERE 
        (filter_metadata IS NULL OR dc.metadata @> filter_metadata)
        AND (1 - (dc.embedding <=> query_embedding)) >= match_threshold
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION rag.search_similar_chunks IS 'Busca chunks similares por embedding';

-- Função para atualizar updated_at
CREATE OR REPLACE FUNCTION rag.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers
CREATE TRIGGER update_doc_chunks_updated_at BEFORE UPDATE ON rag.doc_chunks
    FOR EACH ROW EXECUTE FUNCTION rag.update_updated_at_column();

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON rag.documents
    FOR EACH ROW EXECUTE FUNCTION rag.update_updated_at_column();

-- Grants (opcional)
-- GRANT USAGE ON SCHEMA rag TO llmops_user;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA rag TO llmops_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA rag TO llmops_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA rag TO llmops_user;




