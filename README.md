# 🤖 LLMOps Lab

> Laboratório educacional de arquiteturas LLMOps prontas para produção - Cloud e Local

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

## 🎯 Objetivo

Este repositório é um **laboratório completo** para aprender a construir, avaliar e deployar arquiteturas LLMOps em produção. Cada pipeline é:

- ✅ **Educacional**: Explica conceitos, decisões e trade-offs
- ✅ **Prático**: Código funcional com guias passo-a-passo
- ✅ **Agnóstico**: Funciona em cloud (GCP) e local (VPS/VMs/Docker)
- ✅ **Production-ready**: Observabilidade, governança e testes incluídos

## 📚 Arquiteturas Implementadas

### 1. 🕷️ Crawler Brapi
Coleta automatizada de dados financeiros da B3 via [Brapi API](https://brapi.dev).
- **Conceitos**: ETL, Upsert patterns, Job scheduling
- **Stack**: Python, PostgreSQL, Docker
- **Deploy**: Cloud Run Job + Cloud Scheduler | Cron local
- **[Ver documentação →](pipelines/crawler-brapi/README.md)**

### 2. 🤖 Agentes NL2SQL
Geração de relatórios financeiros usando agentes LangGraph com NL2SQL.
- **Conceitos**: Agentes autônomos, LangGraph, Tool calling, NL2SQL
- **Stack**: LangGraph, OpenRouter, PostgreSQL
- **Deploy**: Cloud Run Service | Docker Compose
- **[Ver documentação →](pipelines/agents/README.md)**

### 3. 📖 Pipeline RAG
Retrieval Augmented Generation com busca vetorial e chunking inteligente.
- **Conceitos**: RAG, Embeddings, Chunking, Busca vetorial
- **Stack**: pgvector, OpenAI Embeddings, FastAPI
- **Deploy**: Cloud Run Job + Service | Docker Compose
- **[Ver documentação →](pipelines/rag/README.md)**

### 4. 🌐 API Blackbox
Gateway LLM com governança, mascaramento PII e geração de datasets.
- **Conceitos**: API Gateway, PII masking, Rate limiting, Dataset generation
- **Stack**: FastAPI, OpenRouter, PostgreSQL
- **Deploy**: Cloud Run Service | Docker Compose
- **[Ver documentação →](pipelines/api-blackbox/README.md)**

---

## 🚀 Quick Start

### Pré-requisitos

- **Docker e Docker Compose** (recomendado)
- **Python 3.11+** (opcional, para desenvolvimento)
- **PostgreSQL 15+** com extensão `pgvector` (via Docker ou instalado)
- **API Keys**: OpenRouter, OpenAI (obtenha em [OpenRouter](https://openrouter.ai) e [OpenAI](https://platform.openai.com))

### Setup Inicial (5 minutos)

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/learning-llmops.git
cd learning-llmops

# 2. Configure variáveis de ambiente
cp env.example .env
# Edite .env com suas credenciais (OPENROUTER_API_KEY, OPENAI_API_KEY, DB_PASSWORD)

# 3. Suba o banco de dados local
make db-up

# 4. Aplique schemas SQL
make db-init
```

### Primeira Vitória: API Blackbox (2 minutos)

```bash
# Inicie a API
cd pipelines/api-blackbox/app
python main.py

# Em outro terminal, teste:
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Explique LLMOps em 2 frases"}],
    "model": "gpt-oss-120b"
  }'
```

### Segunda Vitória: Crawler + Agentes (5 minutos)

```bash
# 1. Execute o crawler para popular dados
cd pipelines/crawler-brapi/app
python main.py --sample

# 2. Gere uma análise com agentes
cd ../../agents/app
python main.py

# Teste a API:
curl -X POST http://localhost:9001/generate_analysis \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "PETR4",
    "analysis_type": "price_movement",
    "period_days": 90
  }'
```

---

## 🐳 Deploy: Cloud ou Local?

Este laboratório foi projetado para funcionar em **ambos os ambientes**:

### ☁️ Deploy em Cloud (GCP)

Cada pipeline tem suporte completo para Google Cloud Platform:
- **Cloud Run**: Serviços serverless escaláveis
- **Cloud Scheduler**: Agendamento de jobs
- **Cloud SQL**: PostgreSQL gerenciado com pgvector
- **Artifact Registry**: Versionamento de imagens Docker
- **Secret Manager**: Gestão segura de credenciais

**Instruções**: Veja o arquivo `DEPLOY.md` em cada pipeline.

### 🏠 Deploy Local/On-Premises

Todas as arquiteturas funcionam localmente ou em VPS/VMs:
- **Docker Compose**: Orquestração de serviços local
- **PostgreSQL + pgvector**: Banco via Docker ou instalado
- **Cron**: Agendamento de jobs (alternativa ao Cloud Scheduler)
- **Nginx**: Reverse proxy (alternativa ao Cloud Run)
- **Docker Registry**: Registry local (alternativa ao Artifact Registry)

**Instruções**: Veja seção "Deploy Local" no README de cada pipeline.

---

## 📂 Estrutura do Projeto

```
learning-llmops/
├── pipelines/               # 🚀 Arquiteturas principais
│   ├── crawler-brapi/       # Crawler de dados Brapi
│   ├── agents/              # Agentes NL2SQL (LangGraph)
│   ├── rag/                 # Pipeline RAG completo
│   └── api-blackbox/        # Gateway OpenRouter
│
├── llmops_lab/              # 📦 Módulos reutilizáveis
│   ├── config/              # Configurações de modelos
│   ├── secrets/             # Secret Manager wrapper
│   ├── logging/             # Logger e tracking de custos
│   ├── db/                  # Conectores SQL
│   └── utils/               # Helpers
│
├── data-schemas/            # 🗄️ Schemas e seeds
│   ├── sql/                 # DDLs do PostgreSQL
│   └── seeds/               # Scripts de ingestão
│
├── docs/                    # 📚 Documentação
│   ├── adr/                 # Architecture Decision Records
│   └── guides/              # Guias detalhados
│
└── scripts/                 # 🔧 Utilitários
```

---

## 🛠️ Stack Tecnológica

- **LLM**: LangChain, LangGraph, OpenAI, OpenRouter
- **Database**: PostgreSQL 15 + pgvector
- **Backend**: FastAPI, Python 3.11+
- **Infra**: Docker, Docker Compose, Cloud Run
- **Observabilidade**: LangSmith, logs estruturados
- **Dados**: Brapi API (mercado financeiro brasileiro)

---

## 📖 Documentação

### Por Arquitetura
- 🕷️ [Crawler Brapi](pipelines/crawler-brapi/README.md) - Coleta de dados financeiros
- 🤖 [Agentes NL2SQL](pipelines/agents/README.md) - Geração de relatórios com LangGraph
- 📖 [Pipeline RAG](pipelines/rag/README.md) - Busca vetorial e geração contextualizada
- 🌐 [API Blackbox](pipelines/api-blackbox/README.md) - Gateway LLM com governança

### Guias Gerais
- 📚 [Architecture Decision Records](docs/adr/) - Decisões arquiteturais documentadas
- 🔧 [Guias Técnicos](docs/guides/) - Setup, deploy e troubleshooting

---

## 🤝 Contribuindo

Este é um projeto educacional aberto. Contribuições são bem-vindas! Veja [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 📝 Licença

MIT License - veja [LICENSE](LICENSE) para detalhes.

---

## 🙏 Créditos

- [Brapi.dev](https://brapi.dev) - API de dados financeiros brasileiros
- [LangChain](https://langchain.com) - Framework para aplicações LLM
- [OpenRouter](https://openrouter.ai) - Gateway multi-modelo

---

**Desenvolvido para a comunidade LLMOps brasileira**
