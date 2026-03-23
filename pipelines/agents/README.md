# Pipeline de Agentes com LangGraph

Sistema de análise de ações da B3 usando agentes inteligentes orquestrados por LangGraph.

---

## 🎯 Conceitos e Por Quê

### O que são Agentes?

Agentes são sistemas de IA que podem **decidir autonomamente** quais ferramentas usar e em que ordem, baseado no contexto e objetivo. Diferente de pipelines fixos, agentes adaptam seu comportamento dinamicamente.

### Por que LangGraph?

**LangGraph** é um framework para construir agentes com **grafos de execução**:
- **Controle explícito**: Você define o fluxo, não deixa tudo na mão do LLM
- **Estado persistente**: Mantém contexto entre etapas
- **Debugging fácil**: Cada nó é rastreável e testável
- **Retry e fallback**: Lógica de recuperação de erros nativa

### Por que usar Agentes para Análise Financeira?

Análises financeiras requerem **múltiplas fontes de dados**:
1. **Dados históricos** (NL2SQL no PostgreSQL)
2. **Contexto de mercado** (WebSearch)
3. **Síntese especializada** (LLM)

Um agente orquestra essas ferramentas de forma inteligente, executando apenas o necessário.

---

## 🏗️ Arquitetura do Sistema

### Visão Geral do Grafo

```
┌─────────┐
│  START  │
└────┬────┘
     │
     ▼
┌─────────┐
│ Router  │ ◄── Decide quais ferramentas usar
└────┬────┘
     │
     ├─────────────┬─────────────┐
     │             │             │
     ▼             ▼             ▼
┌─────────┐   ┌──────────┐  ┌───────────┐
│ NL2SQL  │   │WebSearch │  │  Direct   │
└────┬────┘   └────┬─────┘  └─────┬─────┘
     │             │               │
     └──────┬──────┴───────────────┘
            │
            ▼
     ┌────────────┐
     │ Synthesis  │ ◄── LLM gera análise
     └─────┬──────┘
           │
           ▼
     ┌────────────┐
     │ Validation │ ◄── Valida qualidade
     └─────┬──────┘
           │
      ┌────┴────┐
      │ Retry?  │
      └────┬────┘
           │
        ┌──┴──┐
        │ Sim │ → volta para Synthesis
        └─────┘
           │ Não
           ▼
     ┌────────────┐
     │   Export   │ ◄── Salva arquivo + banco
     └─────┬──────┘
           │
           ▼
       ┌──────┐
       │ End  │
       └──────┘
```

### Componentes Principais

#### 1. Ferramentas (Tools)

**NL2SQL Tool**
- Converte linguagem natural em SQL
- Busca dados históricos de `market.ohlcv`
- Validação de segurança: whitelist de tabelas, blacklist de comandos

**WebSearch Tool**
- Busca contexto de mercado via DuckDuckGo
- Gratuito, sem API key necessária
- Timeout de 10s, máximo 5 resultados

#### 2. Nós do Grafo

**Router**: Decide quais ferramentas executar baseado no tipo de análise
**NL2SQL**: Executa busca de dados históricos
**WebSearch**: Busca contexto web
**Synthesis**: LLM sintetiza análise final
**Validation**: Valida qualidade (tamanho, formato)
**Export**: Salva em arquivo e banco

#### 3. Estado (AgentState)

O estado mantém toda informação durante execução:
```python
{
    "ticker": "PETR4",
    "analysis_type": "price_movement",
    "period_days": 90,
    "nl2sql_data": {...},
    "websearch_data": {...},
    "analysis_content": "# Análise...",
    "tools_used": ["nl2sql", "websearch"],
    "cost_usd": 0.05,
    "errors": []
}
```

### Stack Tecnológica

- **LangGraph**: Orquestração de agentes
- **OpenRouter**: Gateway multi-modelo LLM
- **PostgreSQL**: Banco de dados históricos
- **FastAPI**: API REST
- **Docker**: Containerização

---

## 🚀 Deploy Local

### Pré-requisitos

- Docker e Docker Compose
- PostgreSQL com dados históricos (via crawler-brapi)
- Python 3.11+ (opcional, para desenvolvimento)

### Opção 1: Docker Compose (Recomendado para Produção Local)

```bash
# 1. Configure variáveis de ambiente
cd pipelines/agents
cp .env.example .env
# Edite .env com suas credenciais

# 2. Suba o serviço com Docker Compose
docker-compose up -d

# 3. Verifique logs
docker-compose logs -f agents

# 4. Teste a API
curl http://localhost:9001/health
```

**docker-compose.yml** (criar na raiz de `pipelines/agents/`):
```yaml
version: '3.8'

services:
  agents:
    build:
      context: ../..
      dockerfile: pipelines/agents/Dockerfile.prod
    ports:
      - "9001:8080"
    environment:
      - DB_HOST=${DB_HOST}
      - DB_PASSWORD=${DB_PASSWORD}
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - EXPORTS_DIR=/app/exports
    volumes:
      - ./exports:/app/exports
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Opção 2: Python Local (Desenvolvimento)

```bash
# 1. Configure ambiente
cd pipelines/agents
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou .venv\Scripts\activate  # Windows

# 2. Instale dependências
pip install -r requirements.txt

# 3. Configure variáveis de ambiente
export DB_HOST=localhost
export DB_PASSWORD=sua_senha
export OPENROUTER_API_KEY=sk-or-v1-...
export EXPORTS_DIR=./exports

# 4. Execute a API
cd app
python main.py
```

### Opção 3: Deploy em VPS/VM

Para deploy em servidor próprio (VPS, VM, servidor local):

```bash
# 1. Instale Docker no servidor
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 2. Clone o repositório
git clone https://github.com/seu-repo/learning-llmops.git
cd learning-llmops/pipelines/agents

# 3. Configure .env
nano .env

# 4. Build e execute
docker-compose -f docker-compose.prod.yml up -d

# 5. Configure Nginx como reverse proxy (opcional)
sudo apt install nginx
sudo nano /etc/nginx/sites-available/agents
```

**Nginx config** (`/etc/nginx/sites-available/agents`):
```nginx
server {
    listen 80;
    server_name agents.seudominio.com;

    location / {
        proxy_pass http://localhost:9001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## ☁️ Deploy Cloud (GCP)

Para deploy em produção no Google Cloud Platform, veja [DEPLOY.md](./DEPLOY.md) para:
- Build automático com Cloud Build
- Deploy no Cloud Run
- Versionamento no Artifact Registry
- CI/CD com triggers
- Rollback e recuperação

**Quick deploy**:
```bash
cd pipelines/agents
bash deploy.sh
```

---

## 📡 Uso da API

### Gerar Análise

```bash
POST /generate_analysis
Content-Type: application/json

{
  "ticker": "PETR4",
  "analysis_type": "price_movement",
  "period_days": 90
}
```

**Exemplo**:
```bash
curl -X POST http://localhost:9001/generate_analysis \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "PETR4",
    "analysis_type": "price_movement",
    "period_days": 90
  }'
```

**Resposta**:
```json
{
  "ticker": "PETR4",
  "analysis_type": "price_movement",
  "analysis_content": "# Análise de Movimentação de Preço - PETR4\n\n...",
  "export_path": "exports/analyses/2024-11-14/PETR4_price_movement_20241114_153022.md",
  "tools_used": ["nl2sql", "websearch"],
  "cost_usd": 0.045,
  "latency_ms": 3200,
  "created_at": "2024-11-14T15:30:22Z"
}
```

### Tipos de Análise Disponíveis

1. **price_movement** - Análise de movimentação de preços
2. **volume_analysis** - Análise de volume de negociação
3. **trend_analysis** - Identificação de tendências
4. **support_resistance** - Suportes e resistências
5. **comparative_analysis** - Comparação com índice/setor

### Health Check

```bash
GET /health
```

```bash
curl http://localhost:9001/health
```

---

## 📁 Arquivos de Deploy

### Dockerfile.dev

Imagem Docker para **desenvolvimento local**:
- Hot reload automático (código atualiza sem reiniciar)
- Logs verbosos (DEBUG)
- Cliente PostgreSQL incluído (para debug)

```bash
docker build -f Dockerfile.dev -t agents:dev .
docker run -p 9001:9001 --env-file .env agents:dev
```

### Dockerfile.prod

Imagem Docker **otimizada para produção**:
- Multi-stage build (imagem menor)
- Usuário não-root (segurança)
- Health checks integrados
- Sem ferramentas de desenvolvimento

```bash
docker build -f Dockerfile.prod -t agents:prod .
docker run -p 8080:8080 --env-file .env agents:prod
```

### cloudbuild.yaml

Configuração de **CI/CD para GCP**:
- Build automático da imagem
- Push para Artifact Registry (versionamento)
- Deploy no Cloud Run
- Configuração de recursos (CPU, memória, timeout)

**Processo**: Build → Push → Deploy

### deploy.sh

Script de **deploy automatizado**:
- Validações de ambiente e credenciais
- Deploy interativo com confirmações
- Exibe informações pós-deploy (URL, revisão, logs)

```bash
bash deploy.sh
```

---

## 🔧 Troubleshooting

### Erro: Database Connection Failed

**Sintoma**: `Database health check failed`

**Soluções**:
1. Verifique credenciais no `.env`
2. Teste conexão: `psql $DATABASE_URL -c "SELECT 1"`
3. Verifique se PostgreSQL está rodando: `docker ps`
4. Use Cloud SQL Proxy se necessário (GCP)

### Erro: NL2SQL Tool Failed

**Sintoma**: `Query inválida: Acesso negado à tabela`

**Soluções**:
1. Certifique-se de usar apenas `market.ohlcv`
2. Não use comandos modificadores (INSERT, UPDATE, DELETE)
3. Verifique se dados existem: `SELECT COUNT(*) FROM market.ohlcv WHERE ticker = 'PETR4'`

### Erro: WebSearch Timeout

**Sintoma**: `Busca excedeu timeout de 10s`

**Soluções**:
1. Verifique conexão com internet
2. Tente novamente (instabilidade momentânea)
3. DuckDuckGo pode ter rate limit temporário

### Análise Muito Curta

**Sintoma**: `Validação falhou: Análise muito curta`

**Soluções**:
1. Verifique se ticker existe: `SELECT * FROM market.ohlcv WHERE ticker = 'PETR4' LIMIT 1`
2. Execute crawler para popular dados: `cd ../crawler-brapi && python app/main.py --sample`
3. Tente período maior (ex: 180 dias)

### Custo Muito Alto

**Sintoma**: Análises custando > $0.20

**Soluções**:
1. Verifique modelo configurado em `config.py`
2. Use modelo mais barato: `gpt-oss-120b` ao invés de `claude-3.5-sonnet`
3. Reduza `max_tokens` no prompt

---

## 📚 Documentação Adicional

- **[DEPLOY.md](./DEPLOY.md)** - Deploy avançado em cloud
- **[LangGraph Docs](https://langchain-ai.github.io/langgraph/)** - Documentação oficial
- **[OpenRouter Docs](https://openrouter.ai/docs)** - Gateway multi-modelo

---

## 🤝 Contribuindo

Veja [CONTRIBUTING.md](../../CONTRIBUTING.md) na raiz do projeto.

---

**Desenvolvido com 🤖 pelo Learning LLMOps Team**
