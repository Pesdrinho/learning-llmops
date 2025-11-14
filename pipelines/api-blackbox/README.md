# API Blackbox - Gateway OpenRouter com Governança

Gateway inteligente para modelos LLM via OpenRouter, com controle de custos, mascaramento de PII e observabilidade completa.

---

## 🎯 Conceitos e Por Quê

### O que é um API Gateway?

Um **API Gateway** é uma camada intermediária entre sua aplicação e serviços externos (neste caso, modelos LLM). Ele centraliza:
- **Autenticação e autorização**
- **Rate limiting e controle de custos**
- **Logs e observabilidade**
- **Transformação de dados**
- **Governança e compliance**

### Por que "Blackbox"?

O termo "blackbox" refere-se à **opacidade intencional** dos dados sensíveis:
- Dados PII são **mascarados** antes de enviar ao LLM
- O LLM nunca vê informações sensíveis reais
- Logs armazenam versões mascaradas (compliance com LGPD/GDPR)

### Por que OpenRouter?

**OpenRouter** é um gateway que agrega múltiplos provedores LLM:
- **Uma API, dezenas de modelos**: GPT-4, Claude, Llama, Gemini, etc
- **Billing centralizado**: Uma fatura, múltiplos providers
- **Sem vendor lock-in**: Mude de modelo sem reescrever código
- **Fallback automático**: Se um modelo falha, tenta outro

### Problemas Resolvidos

**1. Custos Descontrolados 💸**
- LLMs cobram por token (~$0.50 a $30 por 1M tokens)
- Loops infinitos ou bugs podem custar milhares
- **Solução**: Rate limit diário (ex: US$ 15/dia)

**2. Dados Sensíveis 🔒**
- CPFs, CNPJs, emails podem vazar em logs
- LGPD/GDPR exigem proteção de PII
- **Solução**: Mascaramento automático via regex

**3. Falta de Observabilidade 📊**
- Difícil rastrear quem está usando quanto
- Logs dispersos e não estruturados
- **Solução**: Logs centralizados no PostgreSQL com tracking de custos

**4. Múltiplos Providers 🔀**
- APIs diferentes para OpenAI, Anthropic, Meta, Google
- Gerenciamento de múltiplas chaves complexo
- **Solução**: OpenRouter unifica todos em uma API

---

## 🏗️ Arquitetura do Sistema

### Fluxo de Requisição

```
Cliente → FastAPI → Middleware (PII Mask + Cost Limit) → OpenRouter → LLM
                         ↓
                  PostgreSQL (logs + costs)
```

### Componentes Principais

#### 1. API (FastAPI)

**Endpoints**:
- `POST /chat` - Chat completion
- `GET /models` - Lista modelos disponíveis
- `GET /health` - Health check

#### 2. Middleware

**PII Masker**:
- Detecta CPF, CNPJ, email, telefone via regex
- Substitui por máscaras antes de enviar ao LLM
- LLM nunca vê dados sensíveis

**Cost Limiter**:
- Calcula custo estimado por request
- Soma com gasto do dia atual
- Bloqueia se >= limite (retorna 429)

#### 3. Guardrails (opcional)

- **Injection Detector**: Detecta prompt injection
- **Topic Validator**: Valida se tópico é permitido
- **Output Validator**: Valida formato da resposta

#### 4. Observabilidade

**Tabela `observability.llm_logs`**:
- Prompt mascarado
- Resposta mascarada
- Tokens usados
- Custo em USD
- Latência em ms
- Timestamp

**Tabela `observability.spend_ledger`**:
- Hash da API key (segurança)
- Modelo usado
- Custo em USD
- Timestamp

### Stack Tecnológica

- **FastAPI**: Framework web moderno e assíncrono
- **OpenRouter**: Gateway multi-modelo
- **PostgreSQL**: Logs e tracking de custos
- **Pydantic**: Validação de dados
- **Docker**: Containerização

---

## 🚀 Deploy Local

### Pré-requisitos

- Docker e Docker Compose
- PostgreSQL (via Docker ou instalado)
- Python 3.11+ (opcional, para desenvolvimento)
- OpenRouter API Key ([obtenha aqui](https://openrouter.ai))

### Opção 1: Docker Compose (Recomendado para Produção Local)

```bash
# 1. Configure variáveis de ambiente
cd pipelines/api-blackbox
cp .env.example .env
# Edite .env com OPENROUTER_API_KEY e DATABASE_URL

# 2. Suba o serviço
docker-compose up -d

# 3. Verifique logs
docker-compose logs -f api-blackbox

# 4. Teste
curl http://localhost:8000/health
```

**docker-compose.yml** (criar na raiz de `pipelines/api-blackbox/`):
```yaml
version: '3.8'

services:
  api-blackbox:
    build:
      context: ../..
      dockerfile: pipelines/api-blackbox/Dockerfile.prod
    ports:
      - "8000:8080"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - BUDGET_USD_DAY=${BUDGET_USD_DAY:-15.0}
      - APP_ENV=production
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Opcional: PostgreSQL local
  postgres:
    image: pgvector/pgvector:pg15
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=llmops
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### Opção 2: Python Local (Desenvolvimento)

```bash
# 1. Configure ambiente
cd pipelines/api-blackbox
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou .venv\Scripts\activate  # Windows

# 2. Instale dependências
pip install -r requirements.txt

# 3. Configure variáveis de ambiente
export OPENROUTER_API_KEY=sk-or-v1-...
export DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/llmops
export BUDGET_USD_DAY=15.0

# 4. Execute a API
cd app
python main.py
```

### Opção 3: Deploy em VPS/VM

Para deploy em servidor próprio:

```bash
# 1. Instale Docker no servidor
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 2. Clone o repositório
git clone https://github.com/seu-repo/learning-llmops.git
cd learning-llmops/pipelines/api-blackbox

# 3. Configure .env
nano .env

# 4. Suba com Docker Compose
docker-compose up -d

# 5. Configure Nginx como reverse proxy
sudo apt install nginx
sudo nano /etc/nginx/sites-available/api-blackbox
```

**Nginx config**:
```nginx
server {
    listen 80;
    server_name api.seudominio.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Rate limiting (adicional ao rate limit da API)
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;
}
```

```bash
# Ativar site
sudo ln -s /etc/nginx/sites-available/api-blackbox /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
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
cd pipelines/api-blackbox
bash deploy.sh
```

---

## 📡 Uso da API

### Chat Completion

```bash
POST /chat
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "Qual a cotação da PETR4?"}
  ],
  "model": "gpt-oss-120b",
  "temperature": 0.7,
  "max_tokens": 500
}
```

**Exemplo**:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Explique LLMOps em 2 frases"}
    ],
    "model": "gpt-oss-120b"
  }'
```

**Resposta**:
```json
{
  "message": {
    "role": "assistant",
    "content": "LLMOps é a prática de operacionalizar modelos LLM..."
  },
  "model": "gpt-oss-120b",
  "usage": {
    "prompt_tokens": 15,
    "completion_tokens": 30,
    "total_tokens": 45
  },
  "cost_usd": 0.0075,
  "latency_ms": 1234,
  "created_at": "2024-11-14T15:30:00Z",
  "request_id": "uuid-here"
}
```

### Modelos Disponíveis

```bash
GET /models
```

```bash
curl http://localhost:8000/models
```

**Resposta**:
```json
{
  "models": [
    {
      "id": "gpt-oss-120b",
      "name": "GPT OSS 120B",
      "provider": "Together",
      "input_cost_per_1k": 0.10,
      "output_cost_per_1k": 0.20,
      "context_window": 4096,
      "description": "Modelo open-source econômico"
    },
    {
      "id": "anthropic/claude-3.5-sonnet",
      "name": "Claude 3.5 Sonnet",
      "provider": "Anthropic",
      "input_cost_per_1k": 3.00,
      "output_cost_per_1k": 15.00,
      "context_window": 200000,
      "description": "Modelo premium de alta qualidade"
    }
  ]
}
```

### Health Check

```bash
GET /health
```

```bash
curl http://localhost:8000/health
```

---

## 🔒 Funcionalidades de Governança

### 1. Mascaramento de PII

**O que é mascarado**:
- CPF: `123.456.789-00` → `***.***.**-**`
- CNPJ: `12.345.678/0001-00` → `**.***.***/****-**`
- Email: `user@example.com` → `***@***.***`
- Telefone: `(11) 98765-4321` → `(11) *****-****`

**Exemplo**:
```python
# Input do usuário
"Meu CPF é 123.456.789-00 e email joao@gmail.com"

# Enviado ao LLM (mascarado)
"Meu CPF é ***.***.**-** e email ***@***.***"

# Log no banco (mascarado)
prompt_masked: "Meu CPF é ***.***.**-** e email ***@***.***"
```

### 2. Controle de Custos

**Limite diário configurável**:
```env
BUDGET_USD_DAY=15.0
```

**Fluxo**:
1. Request chega
2. Calcula custo estimado
3. Soma com gasto do dia (tabela `spend_ledger`)
4. Se >= limite → retorna `429 Too Many Requests`
5. Se < limite → processa normalmente
6. Após processamento → registra custo real

**Cálculo de custo**:
```python
custo_input = (prompt_tokens / 1000) × preço_input_por_1k
custo_output = (completion_tokens / 1000) × preço_output_por_1k
custo_total = custo_input + custo_output
```

### 3. Observabilidade

**Logs estruturados**:
Cada requisição salva em `observability.llm_logs`:
- Prompt mascarado
- Resposta mascarada
- Tokens usados
- Custo em USD
- Latência em ms
- Status (success/error)

**Tracking de custos**:
Cada requisição salva em `observability.spend_ledger`:
- Hash da API key (SHA256)
- Modelo usado
- Custo em USD
- Timestamp

**Consultas úteis**:
```sql
-- Custo por dia
SELECT
  DATE(ts) as dia,
  SUM(cost_usd) as custo_total
FROM observability.spend_ledger
GROUP BY DATE(ts)
ORDER BY dia DESC;

-- Custo por modelo
SELECT
  model,
  COUNT(*) as requests,
  SUM(cost_usd) as custo_total,
  AVG(cost_usd) as custo_medio
FROM observability.spend_ledger
WHERE ts >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY model
ORDER BY custo_total DESC;
```

---

## 📁 Arquivos de Deploy

### Dockerfile.dev

Imagem Docker para **desenvolvimento local**:
- Hot reload automático
- Logs verbosos (DEBUG)
- Sem otimizações de produção

```bash
docker build -f Dockerfile.dev -t api-blackbox:dev .
docker run -p 8000:8000 --env-file .env api-blackbox:dev
```

### Dockerfile.prod

Imagem Docker **otimizada para produção**:
- Multi-stage build (menor tamanho)
- Usuário não-root (segurança)
- Health checks integrados
- Sem ferramentas de desenvolvimento

```bash
docker build -f Dockerfile.prod -t api-blackbox:prod .
docker run -p 8080:8080 --env-file .env api-blackbox:prod
```

### cloudbuild.yaml

Configuração de **CI/CD para GCP**:
- Build automático da imagem
- Push para Artifact Registry (versionamento)
- Deploy no Cloud Run

**Processo**: Build → Push → Deploy

### deploy.sh

Script de **deploy automatizado**:
- Validações de ambiente e credenciais
- Deploy interativo com confirmações
- Exibe informações pós-deploy

```bash
bash deploy.sh
```

---

## 🔧 Troubleshooting

### Erro: OPENROUTER_API_KEY não encontrada

**Sintoma**: `500 Internal Server Error: Missing OPENROUTER_API_KEY`

**Soluções**:
```bash
# .env
OPENROUTER_API_KEY=sk-or-v1-xxx

# Ou Secret Manager (GCP)
gcloud secrets create OPENROUTER_API_KEY --data-file=- <<< "sk-or-v1-xxx"
```

### Erro: 429 - Limite diário excedido

**Sintoma**: `429 Too Many Requests: Daily budget exceeded`

**Soluções**:
1. Aumentar limite: `BUDGET_USD_DAY=30.0`
2. Esperar até meia-noite UTC (reset automático)
3. Limpar spend_ledger (apenas dev):
   ```sql
   DELETE FROM observability.spend_ledger WHERE ts >= CURRENT_DATE;
   ```

### Erro: Database não conectado

**Sintoma**: `500 Internal Server Error: Database connection failed`

**Soluções**:
```bash
# Verifica conectividade
psql $DATABASE_URL -c "SELECT 1"

# Aplica schemas
make db-init

# Verifica se PostgreSQL está rodando
docker ps | grep postgres
```

### Latência alta (>5s)

**Causas comuns**:
1. Modelo lento (GPT-4 é mais lento que GPT-3.5)
2. Prompt muito grande (reduzir contexto)
3. OpenRouter sobrecarregado
4. Rede lenta

**Soluções**:
- Use modelos mais rápidos: `gpt-oss-120b`, `gpt-3.5-turbo`
- Reduza `max_tokens`
- Aumente timeout: `client.timeout = 120.0`

### PII não está sendo mascarado

**Sintoma**: Dados sensíveis aparecem nos logs

**Verificar**:
```python
# Testar regex localmente
from app.middleware.pii_masker import mask_pii

text = "Meu CPF é 123.456.789-00"
masked = mask_pii(text)
print(masked)  # Deve mostrar: "Meu CPF é ***.***.**-**"
```

**Soluções**:
1. Verifique se middleware está ativo
2. Verifique formato dos dados (regex pode não detectar formatos incomuns)
3. Adicione novos padrões no `pii_masker.py`

---

## 📚 Documentação Adicional

- **[DEPLOY.md](./DEPLOY.md)** - Deploy avançado em cloud
- **[PROMPT_LIBRARY.md](./PROMPT_LIBRARY.md)** - Biblioteca de prompts versionados
- **[OpenRouter Docs](https://openrouter.ai/docs)** - Documentação oficial
- **[FastAPI Docs](https://fastapi.tiangolo.com)** - Framework web

---

## 🤝 Contribuindo

Veja [CONTRIBUTING.md](../../CONTRIBUTING.md) na raiz do projeto.

---

**Desenvolvido com ❤️ pelo Learning LLMOps Team**
