# 🤖 LLMOps Lab

> Repositório educacional completo com exemplos práticos de arquiteturas LLMOps para produção

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

## 📚 Visão Geral

O **LLMOps Lab** é um monorepo educacional que demonstra como construir, avaliar e deployar pipelines de LLM em produção. O projeto implementa **5 arquiteturas principais** usando dados financeiros da [Brapi API](https://brapi.dev):

### 🎯 Arquiteturas Implementadas

#### **Quadrante 1: Geração de Documentos e RAG**
1. **🕷️ Crawler Brapi** - Coleta diária de dados financeiros (Cloud Run + Cloud Scheduler)
2. **🤖 Agentes NL2SQL** - Geração de relatórios financeiros via queries SQL (LangGraph)
3. **📖 Pipeline RAG** - Recuperação e geração de respostas contextualizadas (pgvector + OpenAI)

#### **Quadrante 2: Fine-tuning e Tool Use**
4. **🌐 API Blackbox** - Gateway OpenRouter com geração de dataset para tool use
5. **🎓 Fine-tuning** - Treino de modelo especializado (Qwen + LoRA)
6. **🔧 Agentes + MCP** - Agentes com MCP Server para tool calling otimizado

---

## 🏗️ Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                     QUADRANTE 1                             │
│                                                             │
│  Brapi API → Crawler → Cloud SQL (PostgreSQL + pgvector)   │
│                ↓                                            │
│         Agentes NL2SQL → Documentos → Cloud Storage        │
│                              ↓                              │
│                         Pipeline RAG                        │
│                              ↓                              │
│                    Respostas Contextualizadas               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     QUADRANTE 2                             │
│                                                             │
│  API Blackbox (OpenRouter) → Dataset Tool Use → Cloud SQL  │
│                                    ↓                        │
│                            Fine-tuning (Qwen + LoRA)        │
│                                    ↓                        │
│                          Modelo Tool Use                    │
│                                    ↓                        │
│              MCP Server ← Agentes+MCP → Rotas Brapi        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start (10 minutos)

### 1️⃣ Pré-requisitos

- Python 3.10+
- Docker & Docker Compose
- Conta GCP (opcional para produção)
- API Keys: OpenRouter, OpenAI, LangSmith

### 2️⃣ Instalação

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/llmops-lab.git
cd llmops-lab

# Crie e ative ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate  # Windows

# Instale dependências
make dev-install

# Configure variáveis de ambiente
cp env.example .env
# Edite .env com suas credenciais
```

### 3️⃣ Setup do Banco de Dados Local

```bash
# Sobe PostgreSQL com pgvector
make db-up

# Aplica DDLs
make db-init

# Executa seed inicial (amostra de dados)
make seed
```

### 4️⃣ Primeira Vitória: API Blackbox

```bash
# Roda API Blackbox
make api

# Em outro terminal, teste:
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Olá!"}],
    "model": "openrouter/gpt-3.5-turbo"
  }'
```

### 5️⃣ Segunda Vitória: RAG

```bash
# Ingere documentos
make rag-ingest

# Consulta RAG
make rag-query q="Qual o último dividendo da Petrobras?"
```

---

## 📂 Estrutura do Projeto

```
llmops-lab/
├── llmops_lab/              # Módulos exportáveis (reutilizáveis)
│   ├── config/              # Configurações de modelos e preços
│   ├── prompts/             # Prompt Registry (YAML + Jinja)
│   ├── secrets/             # Secret Manager wrapper
│   ├── guards/              # NeMo Guardrails + PII masking
│   ├── logging/             # Logger, custo, tracing (LangSmith)
│   ├── db/                  # Conectores SQL + schemas
│   ├── evals/               # Harness Ragas + métricas
│   ├── utils/               # Cache, rate limit, helpers
│   └── nl2sql/              # Módulo NL2SQL compartilhado
│
├── pipelines/               # Arquiteturas principais
│   ├── crawler-brapi/       # Crawler de dados Brapi
│   ├── agents/              # Agentes NL2SQL (LangGraph)
│   ├── rag/                 # Pipeline RAG completo
│   ├── api-blackbox/        # Gateway OpenRouter
│   ├── fine-tuning/         # Fine-tuning Qwen + LoRA
│   └── agents-mcp/          # Agentes + MCP Server
│
├── data-schemas/            # Schemas SQL e seeds
│   ├── sql/                 # DDLs
│   └── seeds/               # Scripts de ingestão
│
├── docs/                    # Documentação
│   ├── adr/                 # Architecture Decision Records
│   ├── diagrams/            # Diagramas de arquitetura
│   └── guides/              # Guias detalhados
│
├── scripts/                 # Scripts utilitários
├── tests/                   # Testes (unit, integration, e2e)
├── apps/                    # Aplicações integradas
├── .github/workflows/       # CI/CD
├── pyproject.toml           # Dependências
└── Makefile                 # Comandos úteis
```

---

## 🛠️ Tecnologias Utilizadas

### **LLM & AI**
- **LangChain** & **LangGraph** - Orquestração de agentes
- **OpenAI** - Embeddings (text-embedding-3-small)
- **OpenRouter** - Gateway multi-modelo
- **Qwen** - Modelo base para fine-tuning
- **PEFT/LoRA** - Fine-tuning eficiente

### **Database & Storage**
- **PostgreSQL 15** com **pgvector** - Banco vetorial
- **Cloud SQL** - Postgres gerenciado (GCP)
- **Cloud Storage** - Armazenamento de documentos

### **Observabilidade**
- **LangSmith** - Tracing e debugging
- **Ragas** - Avaliação de RAG
- **NeMo Guardrails** - Guardrails básicos

### **Infrastructure**
- **Cloud Run** - Serverless containers
- **Cloud Scheduler** - Agendamento de jobs
- **Secret Manager** - Gestão de segredos

---

## 📊 Dados e Domínio

Todos os pipelines utilizam dados do **mercado financeiro brasileiro** via [Brapi API](https://brapi.dev):

- ✅ **Cotações** de ações (PETR4, VALE3, etc)
- ✅ **Dados históricos** OHLC
- ✅ **Dividendos**
- ✅ **Taxas de câmbio**
- ✅ **Criptomoedas**
- ✅ **SELIC** e **IPCA**

---

## 🎯 Casos de Uso por Arquitetura

### 1. **Crawler Brapi**
- Coleta diária automatizada de dados financeiros
- Upsert inteligente (evita duplicatas)
- Deploy serverless (Cloud Run + Cloud Scheduler)

### 2. **Agentes NL2SQL**
- "Gere relatório de performance da PETR4 em 2024"
- Consulta SQL segura (lista branca de tabelas)
- Geração de documentos markdown

### 3. **Pipeline RAG**
- "Qual foi a variação do Ibovespa no último trimestre?"
- Recuperação de documentos (k=3, cosine similarity)
- Avaliação com Ragas (answer_relevancy, faithfulness)

### 4. **API Blackbox**
- Gateway unificado para múltiplos modelos
- Rate limiting (US$ 15/dia)
- PII masking (CPF, CNPJ, email)
- Geração de dataset para tool use

### 5. **Fine-tuning**
- Especialização em tool calling (rotas Brapi)
- Métrica: 80%+ de acurácia de seleção de ferramenta
- Treino LoRA com Qwen 7B

### 6. **Agentes + MCP**
- MCP Server com rotas Brapi encapsuladas
- Agentes consumindo modelo fine-tunado
- Tool calling otimizado

---

## 🔒 Governança e Segurança

### **Custo**
- ✅ Rate limit diário: **US$ 15**
- ✅ Tracking de custo por request
- ✅ Priorização de modelos locais/baratos

### **Segurança**
- ✅ PII masking (logs)
- ✅ NeMo Guardrails (jailbreak, toxicity)
- ✅ SQL validation (deny-list: DROP, ALTER, DELETE)
- ✅ Secret Manager (GCP)

### **Qualidade**
- ✅ CI Gates: Ragas (RAG) + Tool Accuracy (≥80%)
- ✅ Pre-commit hooks (ruff, mypy)
- ✅ Testes E2E

---

## 📈 Métricas e SLOs

| Pipeline | Métrica Principal | Threshold |
|----------|------------------|-----------|
| RAG | Answer Relevancy (Ragas) | ≥ 0.7 |
| RAG | Faithfulness (Ragas) | ≥ 0.8 |
| Fine-tuning | Tool Selection Accuracy | ≥ 80% |
| API Blackbox | Custo/dia | ≤ US$ 15 |
| Agentes+MCP | Tool Call Success Rate | ≥ 95% |

---

## 🧪 Testes

```bash
# Todos os testes
make test

# Apenas unitários
make test-unit

# Integração
make test-integration

# End-to-end
make test-e2e

# Avaliações
make eval-rag
make eval-tool-use
```

---

## 🚢 Deploy para Produção

### Pré-requisitos GCP (ver `docs/guides/gcp-setup.md`)
1. Criar projeto GCP
2. Habilitar APIs (Cloud SQL, Cloud Run, etc)
3. Configurar Cloud SQL PostgreSQL 15 + pgvector
4. Criar buckets Cloud Storage
5. Configurar Secret Manager

### Deploy dos Serviços

```bash
# Deploy individual
make deploy-crawler   # Crawler Brapi
make deploy-api       # API Blackbox
make deploy-rag       # Pipeline RAG
make deploy-mcp       # MCP Server

# Deploy de tudo
make deploy-all
```

---

## 📖 Documentação Detalhada

- 📘 [Quickstart Guide](docs/guides/quickstart.md)
- 🏗️ [ADR: Decisões de Arquitetura](docs/adr/)
- 🔧 [Setup GCP](docs/guides/gcp-setup.md)
- 🤖 [Guia RAG](pipelines/rag/README.md)
- 🕷️ [Guia Crawler](pipelines/crawler-brapi/README.md)
- 🎓 [Guia Fine-tuning](pipelines/fine-tuning/README.md)
- 🔧 [Guia MCP](pipelines/agents-mcp/README.md)

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Veja [CONTRIBUTING.md](CONTRIBUTING.md) para guidelines.

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/MinhaFeature`)
3. Commit suas mudanças (`git commit -m 'feat: adiciona MinhaFeature'`)
4. Push para a branch (`git push origin feature/MinhaFeature`)
5. Abra um Pull Request

---

## 📝 Licença

Este projeto está sob a licença MIT. Veja [LICENSE](LICENSE) para mais detalhes.

---

## 🙏 Agradecimentos

- [Brapi.dev](https://brapi.dev) - API de dados financeiros
- [LangChain](https://langchain.com) - Framework de LLM
- [OpenRouter](https://openrouter.ai) - Gateway de modelos
- Comunidade LLMOps Brasil

---

## 📞 Contato

Para dúvidas ou sugestões, abra uma [issue](https://github.com/seu-usuario/llmops-lab/issues) ou entre em contato.

---

**Feito com ❤️ para a comunidade LLMOps**
