-- Script de inicialização do PostgreSQL local
-- Habilita a extensão pgvector

-- Cria extensão pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Verifica instalação
SELECT * FROM pg_extension WHERE extname = 'vector';




