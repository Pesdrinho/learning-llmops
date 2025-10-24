# 🚀 API Blackbox - Gateway OpenRouter com Governança

Gateway inteligente para modelos LLM via OpenRouter, com controle de custos, mascaramento de PII e observabilidade completa.

---

## 📚 O Que É e Por Que Existe?

### O Problema

Quando trabalhamos com LLMs diretamente, enfrentamos vários desafios:

1. **Custos Descontrolados** 💸
   - LLMs cobram por token (~US$0.50 a US$30 por 1 milhão de tokens)
   - Loops infinitos ou bugs podem custar milhares
   - Difícil prever gastos mensais

2. **Dados Sensíveis** 🔒
   - CPFs, CNPJs, emails podem vazar em logs
   - LGPD/GDPR exigem proteção de PII
   - Modelos não precisam ver dados sensíveis

3. **Falta de Observabilidade** 📊
   - Difícil rastrear quem está usando
   - Logs dispersos e não estruturados
   - Sem métricas de custo por usuário

4. **Múltiplos Providers** 🔀
   - OpenAI, Anthropic, Meta, Google...
   - APIs diferentes para cada um
   - Gerenciamento de chaves complexo

### A Solução: API Blackbox

Esta API resolve todos esses problemas atuando como um **gateway intermediário** entre sua aplicação e os modelos LLM:

```
Sua App → API Blackbox → OpenRouter → Modelo LLM
              ↓
         [Governança]
         - PII Masking
         - Cost Limiting
         - Logging
         - Metrics
```

---

## 🎯 Funcionalidades

### 1. Gateway OpenRouter

**O que faz:**
- Acessa múltiplos modelos via uma única API
- Fallback automático se um modelo falha
- Routing inteligente para melhor custo-benefício

**Modelos disponíveis:**
- `gpt-oss-120b` - Econômico (~US$0.15/1M tokens)
- `anthropic/claude-3.5-sonnet` - Premium (~US$3-15/1M tokens)
- `openai/gpt-4-turbo` - Alta performance (~US$10-30/1M tokens)
- `openai/gpt-3.5-turbo` - Custo-benefício (~US$0.50/1M tokens)
- `meta-llama/llama-3-70b` - Open-source (~US$0.70/1M tokens)

**Por que OpenRouter?**
- Uma API, dezenas de modelos
- Billing centralizado
- Sem vendor lock-in

### 2. Mascaramento Automático de PII

**O que mascara:**
- CPF: `123.456.789-00` → `***.***.***-**`
- CNPJ: `12.345.678/0001-00` → `**.***.***/****-**`
- Email: `user@example.com` → `***@***.***`
- Telefone: `(11) 98765-4321` → `(11) *****-****`

**Como funciona:**
1. Request chega com dados
2. Regex detecta PII
3. Substitui por máscaras
4. Envia versão mascarada ao LLM
5. LLM nunca vê dados sensíveis

**Exemplo:**
```python
# Entrada
"Meu CPF é 123.456.789-00 e email: joao@gmail.com"

# Mascarado antes de enviar ao LLM
"Meu CPF é ***.***.**

-** e email: ***@***.***"
```

### 3. Controle de Custos

**Limite diário:**
- Padrão: US$15/dia
- Configurável via `BUDGET_USD_DAY`

**Como funciona:**
1. Request chega
2. Calcula custo estimado
3. Soma com gasto do dia
4. Se >= limite → retorna 429 (Too Many Requests)
5. Se < limite → processa normalmente
6. Após processamento → registra custo real

**Cálculo de custo:**
```python
custo_input = (prompt_tokens / 1000) × preço_input_por_1k
custo_output = (completion_tokens / 1000) × preço_output_por_1k
custo_total = custo_input + custo_output
```

**Exemplo:**
```
Modelo: gpt-oss-120b
Input: 1000 tokens × $0.10/1k = $0.10
Output: 500 tokens × $0.20/1k = $0.10
Total: $0.20
```

### 4. Observabilidade Completa

**Logs estruturados:**
Cada requisição salva em `observability.llm_logs`:
- Prompt mascarado
- Resposta mascarada
- Tokens usados
- Custo em USD
- Latência em ms
- Status (success/error)
- Timestamp

**Tracking de custos:**
Cada requisição salva em `observability.spend_ledger`:
- Hash da API key (segurança)
- Modelo usado
- Custo em USD
- Timestamp

**Métricas disponíveis:**
- Custo por usuário
- Custo por modelo
- Latência média
- Taxa de erro
- Tokens por dia

---

## 🚦 Quick Start

### Pré-requisitos

- Python 3.10+
- PostgreSQL com DDLs aplicados
- OpenRouter API Key

### Instalação Local

1. **Configure variáveis de ambiente:**

```bash
# Copie o template
cp env.example .env

# Edite o .env
OPENROUTER_API_KEY=sk-or-v1-xxx
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/llmops
BUDGET_USD_DAY=15.0
```

2. **Instale dependências:**

```bash
pip install -e .
```

3. **Aplique DDLs (se ainda não aplicou):**

```bash
make db-init
```

4. **Rode a API:**

```bash
# Desenvolvimento (hot reload)
cd pipelines/api-blackbox/app
python main.py

# Ou com uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

5. **Acesse a documentação:**

```
http://localhost:8000/docs  # Swagger UI
http://localhost:8000/redoc  # ReDoc
```

---

## 📡 Uso da API

### Endpoint: POST /chat

**Request:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sua-chave-aqui" \
  -d '{
    "messages": [
      {"role": "user", "content": "Qual a cotação da PETR4?"}
    ],
    "model": "gpt-oss-120b",
    "temperature": 0.7,
    "max_tokens": 500
  }'
```

**Response:**
```json
{
  "message": {
    "role": "assistant",
    "content": "A cotação atual da PETR4 é..."
  },
  "model": "gpt-oss-120b",
  "usage": {
    "prompt_tokens": 15,
    "completion_tokens": 30,
    "total_tokens": 45
  },
  "cost_usd": 0.0075,
  "latency_ms": 1234,
  "created_at": "2024-01-15T10:30:00Z",
  "request_id": "uuid-here"
}
```

**Códigos de status:**
- `200` - Sucesso
- `400` - Request inválido
- `429` - Limite diário excedido
- `500` - Erro interno

### Endpoint: GET /models

Lista modelos disponíveis.

**Request:**
```bash
curl http://localhost:8000/models
```

**Response:**
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
    }
  ],
  "total": 5
}
```

### Endpoint: GET /health

Verifica saúde da API.

**Request:**
```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "checks": {
    "database": "ok",
    "openrouter": "ok"
  }
}
```

---

## 🐳 Docker

### Desenvolvimento

```bash
# Build
docker build -f Dockerfile.dev -t api-blackbox:dev .

# Run
docker run -p 8000:8000 \
  --env-file .env \
  api-blackbox:dev
```

### Produção (Cloud Run)

```bash
# Build e deploy
bash deploy.sh
```

Ou manualmente:

```bash
# Build
gcloud builds submit \
  --config=cloudbuild.yaml \
  .

# Deploy já está no cloudbuild.yaml
```

---

## 📊 Monitoramento

### Visualizando Logs

**Local:**
```bash
# Logs da API
tail -f /var/log/api-blackbox.log

# Ou direto do Docker
docker logs -f container-id
```

**Cloud Run:**
```bash
gcloud logging read \
  "resource.type=cloud_run_revision" \
  "resource.labels.service_name=api-blackbox" \
  --limit 50 \
  --format json
```

### Consultas SQL Úteis

**Custo por dia:**
```sql
SELECT 
  DATE(ts) as dia,
  SUM(cost_usd) as custo_total
FROM observability.spend_ledger
GROUP BY DATE(ts)
ORDER BY dia DESC;
```

**Custo por modelo:**
```sql
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

**Latência média:**
```sql
SELECT 
  model,
  AVG(latency_ms) as latencia_media,
  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95
FROM observability.llm_logs
WHERE ts >= CURRENT_DATE - INTERVAL '1 day'
  AND status = 'success'
GROUP BY model;
```

**PII detectado:**
```sql
SELECT 
  DATE(ts) as dia,
  COUNT(*) as total_requests,
  COUNT(CASE WHEN prompt_masked LIKE '%***%' THEN 1 END) as com_pii
FROM observability.llm_logs
WHERE ts >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE(ts);
```

---

## 🔒 Segurança

### API Keys

Sempre use HTTPS em produção.

**Headers recomendados:**
```
Authorization: Bearer sk-or-v1-xxx
```

**Hash de API key no banco:**
- Armazenamos SHA256 da key, não a key em texto claro
- Impossível recuperar key original do hash
- Permite rastrear uso sem expor chaves

### Rate Limiting

Além do limite de custo, considere:

**Nginx rate limiting (prod):**
```nginx
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

location /chat {
    limit_req zone=api burst=20 nodelay;
    proxy_pass http://api-blackbox:8000;
}
```

**CloudFlare (alternativa):**
- 10 requests/segundo por IP
- DDoS protection automático

### CORS

Em produção, configure domínios específicos:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://meu-app.com",
        "https://admin.meu-app.com"
    ],
    allow_credentials=True,
    allow_methods=["POST"],  # Apenas POST
    allow_headers=["Authorization", "Content-Type"],
)
```

---

## 🧪 Testes

```bash
# Testes unitários
pytest pipelines/api-blackbox/tests/test_pii_masker.py
pytest pipelines/api-blackbox/tests/test_cost_limiter.py

# Testes de integração
pytest pipelines/api-blackbox/tests/test_integration.py

# Coverage
pytest --cov=app --cov-report=html
```

---

## 🚨 Troubleshooting

### Erro: "OPENROUTER_API_KEY não encontrada"

**Causa:** API key não configurada  
**Solução:**
```bash
# .env
OPENROUTER_API_KEY=sk-or-v1-xxx

# Ou Secret Manager
gcloud secrets create OPENROUTER_API_KEY --data-file=- <<< "sk-or-v1-xxx"
```

### Erro: 429 - Limite diário excedido

**Causa:** Gasto do dia >= limite configurado  
**Solução:**
1. Aumentar limite: `BUDGET_USD_DAY=30.0`
2. Esperar até meia-noite UTC (reset automático)
3. Limpar spend_ledger (apenas dev):
   ```sql
   DELETE FROM observability.spend_ledger WHERE ts >= CURRENT_DATE;
   ```

### Erro: Database não conectado

**Causa:** DDLs não aplicados ou conexão falhou  
**Solução:**
```bash
# Verifica conectividade
psql $DATABASE_URL -c "SELECT 1"

# Aplica DDLs
make db-init
```

### Latência alta (>5s)

**Possíveis causas:**
1. Modelo lento (GPT-4 é mais lento que 3.5)
2. Prompt muito grande (reduzir contexto)
3. OpenRouter sobrecarregado (retry automático)
4. Rede lenta

**Soluções:**
- Use modelos mais rápidos (`gpt-oss-120b`, `gpt-3.5-turbo`)
- Reduza `max_tokens`
- Aumente timeout: `client.timeout = 120.0`

---

## 📈 Próximos Passos

Depois de dominar a API Blackbox, você está pronto para:

1. **Geração de Dataset para Fine-tuning** (próximo módulo)
2. **Integração com NeMo Guardrails** (segurança avançada)
3. **Deploy em produção no Cloud Run**
4. **Dashboards de monitoramento com Grafana**

---

## 🤝 Contribuindo

Veja [CONTRIBUTING.md](../../CONTRIBUTING.md).

---

## 📚 Referências

- [OpenRouter API Docs](https://openrouter.ai/docs)
- [FastAPI Docs](https://fastapi.tiangolo.com)
- [Pydantic Docs](https://docs.pydantic.dev)
- [LGPD](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm)

---

**Desenvolvido com ❤️ para LLMOps Lab**

*Aprenda fazendo. Crie governança. Escale com confiança.*

