-- ============================================
-- LLMOps Lab - Inicialização do Banco de Dados
-- ============================================

-- Habilita extensão pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Cria schemas principais
CREATE SCHEMA IF NOT EXISTS market;
CREATE SCHEMA IF NOT EXISTS rag;
CREATE SCHEMA IF NOT EXISTS observability;
CREATE SCHEMA IF NOT EXISTS finetune;

-- Comentários dos schemas
COMMENT ON SCHEMA market IS 'Dados de mercado financeiro (Brapi API)';
COMMENT ON SCHEMA rag IS 'Dados para RAG (documentos e embeddings)';
COMMENT ON SCHEMA observability IS 'Logs, métricas e custos';
COMMENT ON SCHEMA finetune IS 'Dados para fine-tuning';

-- Verifica instalação do pgvector
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE NOTICE 'pgvector instalado com sucesso!';
    ELSE
        RAISE EXCEPTION 'pgvector não está instalado';
    END IF;
END $$;
