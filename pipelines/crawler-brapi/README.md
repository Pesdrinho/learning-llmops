# 🕷️ Crawler Brapi - Coleta de Dados Financeiros

Crawler para coleta automatizada de dados do mercado financeiro brasileiro via [Brapi API](https://brapi.dev).

## 📋 Funcionalidades

### Dados Coletados

- ✅ **Cotações** - Preços atuais de ações, FIIs e ETFs
- ✅ **Dados Históricos (OHLCV)** - Preços históricos com volume
- ✅ **Dividendos** - Histórico de proventos
- ✅ **Taxas de Câmbio** - USD-BRL, EUR-BRL, etc
- ✅ **Criptomoedas** - BTC, ETH e outras
- ✅ **Inflação (IPCA)** - Dados mensais de inflação
- ✅ **SELIC** - Taxa básica de juros

### Características

- **Upsert Inteligente**: Evita duplicatas, atualiza dados existentes
- **Rate Limiting**: Respeita limites da API
- **Retry Automático**: Retenta em caso de falhas temporárias
- **Logging Completo**: Rastreamento de todas as operações

---

## 🚀 Quick Start

### Pré-requisitos

- Python 3.10+
- Banco de dados PostgreSQL com DDLs aplicados
- Token Brapi (opcional, para endpoints premium)

### Configuração

1. Configure variáveis de ambiente no `.env`:

```bash
BRAPI_TOKEN=seu_token_aqui  # Opcional
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db
```

2. Aplique DDLs:

```bash
make db-init
```

### Uso Local

#### Modo Sample (Testes)

```bash
# Coleta apenas uma amostra pequena de dados
python pipelines/crawler-brapi/app/main.py --sample
```

#### Modo Completo

```bash
# Coleta todos os dados disponíveis
python pipelines/crawler-brapi/app/main.py
```

---

## 🐳 Docker

### Desenvolvimento

```bash
# Build
docker build -f pipelines/crawler-brapi/Dockerfile.dev -t crawler-brapi:dev .

# Run
docker run --env-file .env crawler-brapi:dev
```

### Produção (Cloud Run)

```bash
# Deploy
cd pipelines/crawler-brapi
bash deploy.sh
```

---

## 📊 Estrutura de Dados

### Assets (market.assets)

```sql
ticker, name, sector, industry, asset_type, currency, metadata
```

### OHLCV (market.ohlcv)

```sql
ticker, date, open, high, low, close, volume, adjusted_close
```

### Dividends (market.dividends)

```sql
ticker, date, type, value, currency, payment_date
```

### FX Rates (market.fx_rates)

```sql
base_currency, quote_currency, date, rate
```

### Crypto (market.crypto_prices)

```sql
symbol, name, date, price_usd, market_cap, volume_24h, change_24h
```

### Inflação (market.inflation_ipca)

```sql
date, value, accumulated_12m
```

### SELIC (market.selic)

```sql
date, rate
```

---

## ⏰ Agendamento Automático

### Cloud Scheduler (Recomendado)

1. Configure job no Cloud Scheduler:

```bash
gcloud scheduler jobs create http crawler-brapi-daily \
    --schedule="0 0 * * *" \
    --uri="https://crawler-brapi-xxxxx.run.app/run" \
    --http-method=POST \
    --time-zone="America/Sao_Paulo"
```

2. O crawler executará diariamente às 00:00

### Cron Local (Alternativa)

```bash
# Adicione ao crontab:
0 0 * * * cd /path/to/llmops-lab && python pipelines/crawler-brapi/app/main.py
```

---

## 🧪 Testes

```bash
# Testes unitários
pytest pipelines/crawler-brapi/tests/test_extractors.py

# Testes de integração (requer banco)
pytest pipelines/crawler-brapi/tests/test_integration.py
```

---

## 📈 Monitoramento

### Logs

Todos os logs são escritos no stdout/stderr e podem ser visualizados:

```bash
# Cloud Run
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=crawler-brapi"

# Local
python pipelines/crawler-brapi/app/main.py 2>&1 | tee crawler.log
```

### Métricas

- **Tickers coletados**: Quantidade de ações processadas
- **Registros OHLCV**: Quantidade de dados históricos
- **Duração**: Tempo total de execução
- **Erros**: Falhas por endpoint

---

## 🔧 Troubleshooting

### Erro: "BRAPI_TOKEN não configurado"

**Causa**: Token não está no `.env`  
**Solução**: Adicione `BRAPI_TOKEN=seu_token` ou use endpoints públicos (limite reduzido)

### Erro: "Database não conectado"

**Causa**: DDLs não foram aplicados ou conexão falhou  
**Solução**:
```bash
make db-up  # Sobe Postgres local
make db-init  # Aplica DDLs
```

### Erro: "Rate limit exceeded"

**Causa**: Muitas requisições em curto período  
**Solução**: Aumente os delays em `main.py` ou use token premium

---

## 📚 Referências

- [Brapi API Docs](https://brapi.dev/docs)
- [Brapi Playground](https://brapi.dev/playground)
- [PostgreSQL pgvector](https://github.com/pgvector/pgvector)

---

## 🤝 Contribuindo

Veja [CONTRIBUTING.md](../../CONTRIBUTING.md) para guidelines.

---

**Desenvolvido com ❤️ para LLMOps Lab**




