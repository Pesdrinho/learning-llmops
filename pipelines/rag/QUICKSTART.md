# RAG Pipeline - Quickstart Guide

Este guia rápido mostra como usar o pipeline RAG completo.

## 🚀 Setup Rápido (5 minutos)

### 1. Configurar Ambiente

```bash
# Criar e ativar ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate  # Windows

# Instalar dependências
pip install -e .
```

### 2. Configurar Variáveis

Crie `.env` na raiz do projeto:

```env
DATABASE_URL_SYNC=postgresql://user:pass@localhost:5432/llmops
OPENAI_API_KEY=sk-...
OPENROUTER_API_KEY=sk-or-...
GCP_PROJECT_ID=seu-projeto-gcp
GCS_BUCKET_NAME=llmops-rag-docs
```

### 3. Inicializar Banco

```bash
# Subir PostgreSQL local
make db-up

# Aplicar schemas (inclui rag.documents e rag.doc_chunks)
make db-init
```

### 4. Upload de Documentos

Coloque seus arquivos Markdown no bucket GCS:

```bash
gsutil cp documentos/*.md gs://llmops-rag-docs/
```

## 📊 Usar o Pipeline

### Vetorização (Processar Documentos)

Execute o job de vetorização para processar documentos do GCS:

```bash
make rag-vectorize
```

**O que acontece:**
- Conecta ao GCS bucket `llmops-rag-docs`
- Lista arquivos `.md` e verifica hash SHA256
- Para cada documento novo/modificado:
  - Aplica chunking (padrão para >5000 chars, dinâmico para ≤5000)
  - Gera embeddings OpenAI (1536 dims)
  - Salva no PostgreSQL com status tracking

**Output esperado:**
```
[INFO] Encontrados 5 arquivos Markdown no bucket llmops-rag-docs
[INFO] Total de documentos a processar: 3
[INFO] Processando documento 1/3: relatorio_petr4_2024
[INFO] Usando StandardChunker (conteúdo: 8500 chars)
[INFO] Documento dividido em 15 chunks
[INFO] Gerados 15 embeddings
[INFO] ✓ Documento relatorio_petr4_2024 processado com sucesso
...
[INFO] Pipeline de Vetorização Finalizado
[INFO] Sucesso: 3 | Falhas: 0
```

### API de Geração (Fazer Queries)

Inicie a API FastAPI:

```bash
make rag-api
```

Em outro terminal, faça queries:

```bash
# Health check
curl http://localhost:8001/health

# Query básica
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Qual foi o último dividendo pago pela Petrobras?"
  }'

# Query com parâmetros customizados
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Qual foi o último dividendo pago pela Petrobras?",
    "top_k": 5,
    "similarity_threshold": 0.8,
    "model": "anthropic/claude-3.5-sonnet"
  }'
```

**Resposta:**
```json
{
  "answer": "A Petrobras (PETR4) anunciou dividendos de R$ 0,50 por ação...",
  "sources": [
    {
      "source_id": "relatorio_petr4_2024",
      "content": "A Petrobras aprovou distribuição...",
      "similarity": 0.92,
      "metadata": {"filename": "relatorio.md"}
    }
  ],
  "metadata": {
    "model": "anthropic/claude-3.5-sonnet",
    "input_tokens": 1500,
    "output_tokens": 250,
    "latency_ms": 1850,
    "chunks_retrieved": 3
  }
}
```

## 🔧 Casos de Uso

### Cenário 1: Perguntas sobre Relatórios Financeiros

```python
import requests

response = requests.post(
    "http://localhost:8001/query",
    json={
        "query": "Quais foram os principais destaques do resultado da Vale no último trimestre?",
        "top_k": 3
    }
)

print(response.json()["answer"])
```

### Cenário 2: Comparações entre Empresas

```python
response = requests.post(
    "http://localhost:8001/query",
    json={
        "query": "Compare os dividendos pagos por Petrobras e Vale em 2024"
    }
)

result = response.json()
print(f"Resposta: {result['answer']}")
print(f"Fontes usadas: {len(result['sources'])}")
```

### Cenário 3: Análise de Indicadores

```python
response = requests.post(
    "http://localhost:8001/query",
    json={
        "query": "Qual foi a variação do EBITDA da Petrobras nos últimos 3 trimestres?"
    }
)
```

## 📋 Comandos Úteis

```bash
# Executar vetorização local
make rag-vectorize

# Iniciar API local
make rag-api

# Deploy do job no GCP
make deploy-rag-job

# Deploy da API no GCP
make deploy-rag-api

# Executar job no GCP
gcloud run jobs execute rag-vectorization_job --region us-central1

# Ver logs do job
gcloud logging read "resource.type=cloud_run_job" --limit 50

# Ver logs da API
gcloud logging read "resource.type=cloud_run_revision" --limit 50
```

## 🐛 Troubleshooting

### Erro: "No chunks retrieved"

**Causa:** Documentos não foram vetorizados ou threshold muito alto.

**Solução:**
```bash
# 1. Verificar se há documentos processados
psql $DATABASE_URL -c "SELECT source_id, status FROM rag.documents;"

# 2. Executar vetorização
make rag-vectorize

# 3. Tentar query com threshold menor
curl -X POST http://localhost:8001/query \
  -d '{"query": "...", "similarity_threshold": 0.5}'
```

### Erro: "Connection refused" PostgreSQL

**Causa:** Banco não está rodando ou URL incorreta.

**Solução:**
```bash
# Verificar se o banco está up
make db-up

# Testar conexão
psql $DATABASE_URL -c "SELECT 1;"
```

### Erro: OpenAI rate limit

**Causa:** Muitas requisições simultâneas para API da OpenAI.

**Solução:**
- Processar documentos em batches menores
- Adicionar delay entre batches
- Usar batch size menor em `config.py`

### Erro: GCS permission denied

**Causa:** Service account sem permissão no bucket.

**Solução:**
```bash
# Verificar service account
gcloud auth list

# Dar permissão ao bucket
gsutil iam ch serviceAccount:SA@PROJECT.iam.gserviceaccount.com:objectViewer \
  gs://llmops-rag-docs
```

## 📊 Monitoramento

### Ver documentos processados

```sql
SELECT
    source_id,
    status,
    total_chunks,
    processed_at
FROM rag.documents
ORDER BY processed_at DESC;
```

### Ver chunks por documento

```sql
SELECT
    source_id,
    COUNT(*) as num_chunks,
    AVG(LENGTH(content)) as avg_chunk_size
FROM rag.doc_chunks
GROUP BY source_id;
```

### Testar busca vetorial direta

```sql
-- Buscar chunks similares (substitua o embedding por um real)
SELECT
    source_id,
    content,
    1 - (embedding <=> '[0.1, 0.2, ...]'::vector(1536)) as similarity
FROM rag.doc_chunks
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector(1536)
LIMIT 5;
```

## 🎯 Próximos Passos

1. **Adicionar mais documentos**: Upload contínuo no GCS
2. **Customizar prompts**: Editar `generation_api/prompts/rag.py`
3. **Ajustar chunking**: Modificar thresholds em `config.py`
4. **Implementar cache**: Adicionar Redis para queries repetidas
5. **Adicionar avaliação**: Integrar Ragas para métricas de qualidade

## 📚 Links Úteis

- [README Completo](./README.md)
- [Documentação da API](http://localhost:8001/docs) (quando rodando)
- [Schema do Banco](../../data-schemas/sql/02_rag_schema.sql)
- [Planejamento Original](../../.cursor/PLANEJAMENTO.md)
