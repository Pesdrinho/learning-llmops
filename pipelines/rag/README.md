# Pipeline RAG - Retrieval Augmented Generation

Sistema completo de RAG (Retrieval Augmented Generation) com busca vetorial e chunking inteligente, composto por dois serviços independentes.

---

## 🎯 Conceitos e Por Quê

### O que é RAG?

**RAG (Retrieval Augmented Generation)** é uma técnica que combina:
1. **Retrieval (Recuperação)**: Busca documentos relevantes em uma base de conhecimento
2. **Augmentation (Aumento)**: Adiciona documentos recuperados ao contexto do LLM
3. **Generation (Geração)**: LLM gera resposta baseado no contexto enriquecido

### Por que RAG?

**Problema**: LLMs têm limitações:
- ❌ **Knowledge cutoff**: Dados desatualizados (ex: GPT-4 tem cutoff em 2023)
- ❌ **Hallucination**: Inventam informações quando não sabem
- ❌ **Domínio específico**: Não sabem sobre seus dados proprietários

**Solução**: RAG resolve isso:
- ✅ **Dados atualizados**: Busca em base de conhecimento atual
- ✅ **Baseado em fatos**: Resposta fundamentada em documentos reais
- ✅ **Domínio específico**: Usa seus documentos proprietários

### Componentes do RAG

**1. Chunking**: Dividir documentos em pedaços menores
- Documentos longos não cabem no contexto do LLM
- Chunks menores = buscas mais precisas

**2. Embeddings**: Converter texto em vetores numéricos
- Permite comparar similaridade entre textos
- Busca vetorial é mais eficiente que busca textual

**3. Vector Database**: Armazenar e buscar embeddings
- pgvector: extensão PostgreSQL para busca vetorial
- Similaridade cosseno: métrica de distância entre vetores

**4. Retrieval**: Buscar chunks mais relevantes
- Top-k: retorna k chunks mais similares à query
- Threshold: filtra chunks com similaridade < threshold

**5. Generation**: LLM gera resposta com contexto
- Prompt inclui chunks recuperados
- LLM sintetiza resposta baseada nos chunks

### Arquitetura: 2 Serviços

Este pipeline tem **2 serviços independentes**:

**1. Vectorization Job** (Cloud Run Job)
- Executa periodicamente (ex: diariamente)
- Processa documentos novos/modificados do GCS
- Gera chunks e embeddings
- Salva no PostgreSQL

**2. Generation API** (Cloud Run Service)
- API REST sempre disponível
- Recebe queries dos usuários
- Busca chunks relevantes
- Gera respostas com LLM

**Por que separar?**
- ✅ **Escalabilidade**: Job pesado roda quando necessário, API leve sempre disponível
- ✅ **Custos**: Job não consome recursos quando não está executando
- ✅ **Independência**: Atualizar vectorização não afeta API e vice-versa

---

## 🏗️ Arquitetura do Sistema

### Fluxo Completo

```
┌──────────────┐
│ Documentos   │
│ (.md no GCS) │
└──────┬───────┘
       │
       ▼
┌──────────────────────┐
│ Vectorization Job    │
│ 1. Carrega docs      │
│ 2. Detecta mudanças  │
│ 3. Chunking          │
│ 4. Embeddings        │
│ 5. Salva no PG       │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ PostgreSQL (pgvector)│
│ - rag.documents      │
│ - rag.doc_chunks     │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ Generation API       │
│ 1. Recebe query      │
│ 2. Embedding query   │
│ 3. Busca vetorial    │
│ 4. Prompt + contexto │
│ 5. LLM gera resposta │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ Resposta ao usuário  │
│ + Fontes             │
└──────────────────────┘
```

### Stack Tecnológica

- **OpenAI Embeddings**: text-embedding-3-small (1536 dims)
- **pgvector**: Extensão PostgreSQL para busca vetorial
- **OpenRouter**: Gateway multi-modelo para geração
- **Gemini 2.5 Flash**: Chunking dinâmico inteligente
- **FastAPI**: API REST assíncrona
- **Google Cloud Storage**: Armazenamento de documentos

---

## 🚀 Deploy Local

### Pré-requisitos

- Docker e Docker Compose
- PostgreSQL 15+ com extensão pgvector
- Python 3.11+ (opcional)
- Google Cloud Storage bucket (ou storage local)
- API Keys: OpenAI, OpenRouter

### Opção 1: Docker Compose (Recomendado)

```bash
# 1. Configure variáveis de ambiente
cd pipelines/rag
cp .env.example .env
# Edite .env com credenciais

# 2. Suba todos os serviços
docker-compose up -d

# 3. Verifique logs
docker-compose logs -f

# 4. Execute vectorização
docker-compose exec vectorization python main.py

# 5. Teste API
curl http://localhost:8001/health
```

**docker-compose.yml** (criar na raiz de `pipelines/rag/`):
```yaml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg15
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=llmops
    volumes:
      - postgres_data:/var/lib/postgresql/data

  vectorization:
    build:
      context: ../..
      dockerfile: pipelines/rag/vectorization_job/Dockerfile
    environment:
      - DATABASE_URL_SYNC=${DATABASE_URL_SYNC}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - GCS_BUCKET_NAME=${GCS_BUCKET_NAME}
    volumes:
      - ./docs:/app/docs  # Alternativa: usar pasta local ao invés de GCS
    depends_on:
      - postgres
    profiles:
      - manual  # Não inicia automaticamente, executar manualmente

  generation-api:
    build:
      context: ../..
      dockerfile: pipelines/rag/generation_api/Dockerfile
    ports:
      - "8001:8080"
    environment:
      - DATABASE_URL_SYNC=${DATABASE_URL_SYNC}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
    depends_on:
      - postgres
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  postgres_data:
```

### Opção 2: Python Local (Desenvolvimento)

**Vectorization Job**:
```bash
# 1. Ambiente
cd pipelines/rag/vectorization_job
python -m venv .venv
source .venv/bin/activate

# 2. Dependências
pip install -r requirements.txt

# 3. Variáveis
export DATABASE_URL_SYNC=postgresql://user:pass@localhost:5432/llmops
export OPENAI_API_KEY=sk-...
export GCS_BUCKET_NAME=llmops-rag-docs

# 4. Executar
python main.py
```

**Generation API**:
```bash
# 1. Ambiente
cd pipelines/rag/generation_api
python -m venv .venv
source .venv/bin/activate

# 2. Dependências
pip install -r requirements.txt

# 3. Variáveis
export DATABASE_URL_SYNC=postgresql://user:pass@localhost:5432/llmops
export OPENAI_API_KEY=sk-...
export OPENROUTER_API_KEY=sk-or-v1-...

# 4. Executar
uvicorn main:app --reload --port 8001
```

### Opção 3: Deploy em VPS/VM

```bash
# 1. Instale Docker no servidor
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 2. Clone repositório
git clone https://github.com/seu-repo/learning-llmops.git
cd learning-llmops/pipelines/rag

# 3. Configure .env
nano .env

# 4. Suba serviços
docker-compose up -d generation-api

# 5. Configure Nginx
sudo nano /etc/nginx/sites-available/rag-api
```

**Nginx config**:
```nginx
server {
    listen 80;
    server_name rag.seudominio.com;

    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Agendamento do job de vectorização** (cron):
```bash
# Editar crontab
crontab -e

# Executar diariamente às 2h AM
0 2 * * * cd /path/to/learning-llmops/pipelines/rag && docker-compose run --rm vectorization >> /var/log/rag-vectorization.log 2>&1
```

---

## ☁️ Deploy Cloud (GCP)

Para deploy completo no Google Cloud Platform, veja [DEPLOY.md](./DEPLOY.md) para:
- Vectorization Job: Build, deploy, agendamento com Cloud Scheduler
- Generation API: Build, deploy, auto-scaling
- Versionamento no Artifact Registry
- CI/CD com triggers
- Rollback e recuperação

**Quick deploy**:
```bash
# Deploy job de vectorização
cd pipelines/rag/vectorization_job
bash deploy.sh

# Deploy API de geração
cd ../generation_api
bash deploy.sh
```

---

## 📡 Uso da API

### Query RAG

```bash
POST /query
Content-Type: application/json

{
  "query": "Qual foi o último dividendo pago pela Petrobras?",
  "top_k": 3,
  "similarity_threshold": 0.7
}
```

**Exemplo**:
```bash
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Qual foi a variação do Ibovespa no último trimestre?",
    "top_k": 3,
    "similarity_threshold": 0.7
  }'
```

**Resposta**:
```json
{
  "answer": "No último trimestre, o Ibovespa apresentou variação de +8,5%...",
  "sources": [
    {
      "source_id": "relatorio_ibov_2024",
      "content": "O índice Ibovespa encerrou o trimestre com alta acumulada de 8,5%...",
      "similarity": 0.92,
      "metadata": {
        "filename": "relatorio_ibovespa_q3_2024.md",
        "chunk_index": 2
      }
    },
    {
      "source_id": "analise_mercado_2024",
      "content": "A bolsa brasileira teve desempenho positivo...",
      "similarity": 0.87,
      "metadata": {
        "filename": "analise_mercado.md",
        "chunk_index": 5
      }
    }
  ],
  "metadata": {
    "model": "anthropic/claude-3.5-sonnet",
    "input_tokens": 1500,
    "output_tokens": 250,
    "latency_ms": 1850,
    "chunks_retrieved": 3,
    "embedding_time_ms": 120,
    "retrieval_time_ms": 45,
    "generation_time_ms": 1685
  }
}
```

### Health Check

```bash
GET /health
```

```bash
curl http://localhost:8001/health
```

---

## 🔧 Configurações

### Chunking

**Estratégia Híbrida**:
- **Documentos > 5000 chars**: Chunking padrão (500 tokens, overlap 100)
- **Documentos ≤ 5000 chars**: Chunking dinâmico com Gemini 2.5 Flash

**Por quê?**
- Documentos grandes: Chunking padrão é rápido e eficiente
- Documentos pequenos: LLM identifica divisões semânticas naturais

### Embeddings

- **Modelo**: `text-embedding-3-small`
- **Dimensões**: 1536
- **Batch size**: 100 chunks por request
- **Custo**: ~$0.02 por 1M tokens

### Geração

- **Modelo padrão**: `anthropic/claude-3.5-sonnet`
- **Temperature**: 0.3 (mais determinístico)
- **Max tokens**: 2000
- **Prompt**: Versionado (v1.0.0)

### Busca Vetorial

- **Métrica**: Similaridade cosseno
- **Top-k padrão**: 3 chunks
- **Similarity threshold**: 0.7 (70% de similaridade mínima)
- **Índice**: ivfflat (pgvector)

---

## 📁 Arquivos de Deploy

### vectorization_job/Dockerfile

Imagem Docker para **job de vectorização**:
- Processa documentos do GCS
- Gera chunks e embeddings
- Multi-stage build (otimizado)

### generation_api/Dockerfile

Imagem Docker para **API de geração**:
- Expõe endpoint REST
- Busca vetorial no PostgreSQL
- Gera respostas com LLM

### vectorization_job/cloudbuild.yaml

Deploy como **Cloud Run Job**:
- Executa e termina (não fica rodando)
- Agendável via Cloud Scheduler

### generation_api/cloudbuild.yaml

Deploy como **Cloud Run Service**:
- API sempre disponível
- Auto-scaling baseado em tráfego

### deploy.sh (ambos)

Scripts de deploy automatizado para cada serviço.

---

## 🔧 Troubleshooting

### Vectorização: No chunks retrieved

**Sintoma**: API retorna `No chunks found for query`

**Causas**:
1. Job de vectorização não executou
2. Documentos vazios ou inexistentes no GCS
3. Threshold de similaridade muito alto

**Soluções**:
```bash
# 1. Verificar se há chunks no banco
psql $DATABASE_URL -c "SELECT COUNT(*) FROM rag.doc_chunks"

# 2. Executar vectorização manualmente
cd pipelines/rag/vectorization_job
python main.py

# 3. Baixar threshold
curl -X POST http://localhost:8001/query \
  -d '{"query": "test", "similarity_threshold": 0.5}'
```

### API: OpenAI rate limit

**Sintoma**: `RateLimitError: You exceeded your current quota`

**Soluções**:
1. Adicione créditos na conta OpenAI
2. Use batch embeddings menores (reduzir de 100 para 50)
3. Adicione retry logic com backoff

### Job: Timeout

**Sintoma**: Job termina antes de processar todos os documentos

**Soluções**:
```bash
# Aumentar timeout (GCP)
gcloud run jobs update rag-vectorization-job \
  --timeout=3600 \
  --region=us-central1

# Ou processar menos documentos por execução
```

### Respostas Genéricas (Hallucination)

**Sintoma**: LLM responde sem usar chunks recuperados

**Causas**:
1. Chunks não relacionados à query (baixa similaridade)
2. Prompt não força uso dos chunks
3. Modelo muito criativo (temperature alta)

**Soluções**:
1. Aumentar top_k (buscar mais chunks)
2. Melhorar prompt: "APENAS responda com base nos documentos fornecidos"
3. Reduzir temperature (0.0 - 0.3)

### Latência Alta (>5s)

**Causas**:
1. Geração do LLM (mais lento)
2. Busca vetorial sem índice otimizado
3. Embeddings da query demoram

**Otimizações**:
```sql
-- Otimizar índice pgvector
CREATE INDEX idx_doc_chunks_embedding ON rag.doc_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Vacuum e analyze
VACUUM ANALYZE rag.doc_chunks;
```

```bash
# Usar modelo mais rápido
# Em generation_api/config.py, mudar para:
DEFAULT_MODEL = "openai/gpt-3.5-turbo"  # Mais rápido que Claude
```

---

## 📚 Documentação Adicional

- **[DEPLOY.md](./DEPLOY.md)** - Deploy avançado em cloud (detalhado)
- **[DEBUGGING.md](./DEBUGGING.md)** - Guia de debugging (caso exista)
- **[QUICKSTART.md](./QUICKSTART.md)** - Guia rápido (caso exista)
- **[OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)** - Documentação oficial
- **[pgvector](https://github.com/pgvector/pgvector)** - Extensão PostgreSQL
- **[OpenRouter](https://openrouter.ai/docs)** - Gateway multi-modelo

---

## 🤝 Contribuindo

Veja [CONTRIBUTING.md](../../CONTRIBUTING.md) na raiz do projeto.

---

**Desenvolvido com 📖 pelo Learning LLMOps Team**
