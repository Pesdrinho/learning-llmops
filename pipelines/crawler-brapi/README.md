# Crawler Brapi - Coleta de Dados Financeiros

Crawler automatizado para coleta de dados do mercado financeiro brasileiro via [Brapi API](https://brapi.dev).

---

## 🎯 Conceitos e Por Quê

### O que é um Crawler/ETL?

Um **crawler** (ou job ETL - Extract, Transform, Load) é um processo que:
1. **Extrai** dados de uma fonte externa (API, website, database)
2. **Transforma** os dados (limpa, normaliza, enriquece)
3. **Carrega** os dados em um destino (database, data lake, cache)

### Por que Coletar Dados Financeiros?

Dados históricos são essenciais para:
- **Análises técnicas**: Identificar tendências, suportes, resistências
- **Machine Learning**: Treinar modelos preditivos
- **RAG**: Gerar respostas contextualizadas sobre o mercado
- **Dashboards**: Visualizar performance de ativos

### Por que Brapi API?

**Brapi** é uma API brasileira gratuita que agrega dados de:
- **B3** (Bolsa de Valores brasileira)
- **Yahoo Finance**
- **Banco Central** (SELIC, IPCA)

**Vantagens**:
- ✅ Gratuita para uso básico
- ✅ Dados brasileiros (PETR4, VALE3, etc)
- ✅ Múltiplos endpoints (cotações, dividendos, câmbio, cripto)
- ✅ Sem necessidade de cadastro para maioria dos endpoints

### Pattern: Upsert

Este crawler usa **upsert** (update + insert):
- **Se registro já existe**: atualiza (evita duplicatas)
- **Se registro não existe**: insere

**Vantagem**: Idempotência - executar múltiplas vezes não gera dados duplicados.

### Pattern: Job Scheduling

Dados financeiros são atualizados diariamente. O crawler deve executar:
- **Cloud**: Cloud Scheduler + Cloud Run Job (GCP)
- **Local**: Cron (Linux/Mac) ou Task Scheduler (Windows)

---

## 🏗️ Arquitetura do Sistema

### Fluxo de Execução

```
┌──────────┐      ┌──────────────┐      ┌──────────────┐      ┌──────────┐
│ Scheduler│ ───▶ │ Crawler Main │ ───▶ │ Extractors   │ ───▶ │ Loaders  │
│ (Trigger)│      │ (Orchestrator)│      │ (Brapi API)  │      │ (Postgres)│
└──────────┘      └──────────────┘      └──────────────┘      └──────────┘
                         │
                         ▼
                  ┌──────────────┐
                  │ Retry Logic  │
                  │ + Rate Limit │
                  └──────────────┘
```

### Componentes Principais

#### 1. Extractors

Cada extractor é responsável por um tipo de dado:

**quotes.py** - Cotações atuais
- Endpoint: `/quote/{ticker}`
- Dados: Preço atual, variação, volume

**ohlcv.py** - Dados históricos
- Endpoint: `/quote/{ticker}?range=1y`
- Dados: Open, High, Low, Close, Volume (OHLCV)

**dividends.py** - Dividendos pagos
- Endpoint: `/quote/{ticker}?modules=dividendsData`
- Dados: Data de pagamento, valor, tipo

**fx_rates.py** - Taxas de câmbio
- Endpoint: `/v2/currency`
- Dados: USD-BRL, EUR-BRL, etc

**crypto.py** - Criptomoedas
- Endpoint: `/v2/crypto`
- Dados: BTC, ETH, preços em BRL

**inflation.py** - Inflação (IPCA)
- Endpoint: `/v2/inflation`
- Dados: IPCA mensal e acumulado

#### 2. Loaders

**loaders.py** - Persistência no PostgreSQL
- Usa `INSERT ... ON CONFLICT DO UPDATE` (upsert)
- Transações para garantir consistência
- Logging de sucesso/erro

#### 3. Rate Limiting

Brapi API tem limites:
- **Sem token**: 50 requests/minuto
- **Com token**: 200 requests/minuto

**Estratégia**: Adicionar delays entre requests (1-2s)

### Stack Tecnológica

- **Python 3.11+**: Linguagem principal
- **httpx**: Cliente HTTP assíncrono
- **PostgreSQL**: Banco de dados
- **Docker**: Containerização
- **Cloud Scheduler + Cloud Run Job**: Agendamento (GCP)
- **Cron**: Agendamento (local/VPS)

---

## 🚀 Deploy Local

### Pré-requisitos

- Docker (opcional)
- Python 3.11+
- PostgreSQL com schemas aplicados
- Token Brapi (opcional, para mais requests)

### Opção 1: Docker (Recomendado)

```bash
# 1. Configure variáveis de ambiente
cd pipelines/crawler-brapi
cp .env.example .env
# Edite .env com DATABASE_URL e BRAPI_TOKEN (opcional)

# 2. Build da imagem
docker build -f Dockerfile.prod -t crawler-brapi:latest .

# 3. Execute o crawler
docker run --env-file .env crawler-brapi:latest

# Para modo sample (apenas amostra de dados):
docker run --env-file .env crawler-brapi:latest python app/main.py --sample
```

### Opção 2: Python Local

```bash
# 1. Configure ambiente
cd pipelines/crawler-brapi
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou .venv\Scripts\activate  # Windows

# 2. Instale dependências
pip install -r requirements.txt

# 3. Configure variáveis de ambiente
export DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/llmops
export BRAPI_TOKEN=seu_token  # Opcional

# 4. Execute o crawler
python app/main.py

# Modo sample (apenas amostra):
python app/main.py --sample
```

### Opção 3: Deploy em VPS/VM com Cron

Para execução diária automatizada em servidor próprio:

```bash
# 1. Instale Docker no servidor
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 2. Clone o repositório
git clone https://github.com/seu-repo/learning-llmops.git
cd learning-llmops/pipelines/crawler-brapi

# 3. Configure .env
nano .env

# 4. Build da imagem
docker build -f Dockerfile.prod -t crawler-brapi:latest .

# 5. Teste execução manual
docker run --env-file .env crawler-brapi:latest

# 6. Configure cron para execução diária
crontab -e
```

**Crontab entry** (executar diariamente às 2h AM):
```cron
0 2 * * * cd /path/to/learning-llmops/pipelines/crawler-brapi && docker run --env-file .env crawler-brapi:latest >> /var/log/crawler-brapi.log 2>&1
```

**Alternativa com Docker Compose + cron interno**:

**docker-compose.yml**:
```yaml
version: '3.8'

services:
  crawler-brapi:
    build:
      context: ../..
      dockerfile: pipelines/crawler-brapi/Dockerfile.prod
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - BRAPI_TOKEN=${BRAPI_TOKEN}
    restart: "no"
    command: python app/main.py
```

**Script de agendamento** (`run_crawler.sh`):
```bash
#!/bin/bash
cd /path/to/learning-llmops/pipelines/crawler-brapi
docker-compose up --abort-on-container-exit
docker-compose down
```

**Crontab**:
```cron
0 2 * * * /path/to/run_crawler.sh >> /var/log/crawler-brapi.log 2>&1
```

---

## ☁️ Deploy Cloud (GCP)

Para deploy em produção no Google Cloud Platform como **Cloud Run Job**, veja [DEPLOY.md](./DEPLOY.md) para:
- Build automático com Cloud Build
- Deploy como Cloud Run Job (não Service)
- Agendamento com Cloud Scheduler
- Versionamento no Artifact Registry
- Execução sob demanda ou agendada

**Quick deploy**:
```bash
cd pipelines/crawler-brapi
bash deploy.sh
```

**Agendar execução diária**:
```bash
# Criar job no Cloud Scheduler
gcloud scheduler jobs create http crawler-brapi-daily \
  --schedule="0 2 * * *" \
  --uri="https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/PROJECT_ID/jobs/crawler-brapi:run" \
  --http-method=POST \
  --oauth-service-account-email="SA_EMAIL@PROJECT_ID.iam.gserviceaccount.com" \
  --time-zone="America/Sao_Paulo"
```

---

## 📊 Dados Coletados

### Tabelas Populadas

**market.assets**
- Ticker, nome, setor, tipo de ativo

**market.ohlcv**
- Dados históricos OHLC + Volume
- Usado por: Agentes NL2SQL, análises técnicas

**market.dividends**
- Histórico de dividendos pagos

**market.fx_rates**
- Taxas de câmbio (USD-BRL, EUR-BRL, etc)

**market.crypto_prices**
- Preços de criptomoedas em BRL

**market.inflation_ipca**
- Dados mensais de inflação (IPCA)

**market.selic**
- Taxa básica de juros (SELIC)

### Verificar Dados

```sql
-- Contar registros por tabela
SELECT COUNT(*) FROM market.assets;
SELECT COUNT(*) FROM market.ohlcv;
SELECT COUNT(*) FROM market.dividends;

-- Ver últimas cotações
SELECT * FROM market.ohlcv
WHERE ticker = 'PETR4'
ORDER BY date DESC
LIMIT 10;

-- Ver dividendos de PETR4
SELECT * FROM market.dividends
WHERE ticker = 'PETR4'
ORDER BY date DESC;
```

---

## 📁 Arquivos de Deploy

### Dockerfile.dev

Imagem Docker para **desenvolvimento/debug**:
- Cliente PostgreSQL incluído (psql)
- Logs verbosos
- Sem otimizações

```bash
docker build -f Dockerfile.dev -t crawler-brapi:dev .
docker run --env-file .env crawler-brapi:dev
```

### Dockerfile.prod

Imagem Docker **otimizada para produção**:
- Multi-stage build (menor tamanho)
- Apenas dependências necessárias
- Usuário não-root (segurança)

```bash
docker build -f Dockerfile.prod -t crawler-brapi:prod .
docker run --env-file .env crawler-brapi:prod
```

### cloudbuild.yaml

Configuração de **CI/CD para GCP**:
- Build automático da imagem
- Push para Artifact Registry (versionamento)
- Deploy como Cloud Run Job (não Service)

**Diferença Job vs Service**:
- **Job**: Executa e termina (ideal para crawlers)
- **Service**: Fica rodando (ideal para APIs)

### deploy.sh

Script de **deploy automatizado**:
- Validações de ambiente
- Build via Cloud Build
- Deploy como Cloud Run Job
- Teste de execução

```bash
bash deploy.sh
```

---

## 🔧 Troubleshooting

### Erro: BRAPI_TOKEN não configurado

**Sintoma**: Warnings ou rate limit excedido

**Solução**:
- Token **não é obrigatório** para endpoints básicos
- Obtenha em: https://brapi.dev
- Configure no `.env`: `BRAPI_TOKEN=seu_token`

### Erro: Database Connection Failed

**Sintoma**: `Connection refused` ou `Database not found`

**Soluções**:
```bash
# Verifica conectividade
psql $DATABASE_URL -c "SELECT 1"

# Aplica schemas (se ainda não aplicou)
make db-init

# Verifica se PostgreSQL está rodando
docker ps | grep postgres
```

### Erro: Rate Limit Exceeded

**Sintoma**: `429 Too Many Requests` da Brapi API

**Soluções**:
1. **Use token Brapi**: Aumenta limite de 50 para 200 req/min
2. **Aumente delays**: No código, aumente tempo entre requests
3. **Modo sample**: Execute com `--sample` para coletar menos dados

### Dados Não Atualizando

**Sintoma**: Mesmos dados após executar crawler

**Causas comuns**:
1. **Fim de semana/feriado**: Bolsa fechada, sem novos dados
2. **Horário de execução**: Execute após fechamento da bolsa (18h+)
3. **Upsert funcionando**: Dados já existem, não há duplicatas

**Verificar**:
```sql
-- Ver última atualização
SELECT MAX(updated_at) FROM market.ohlcv WHERE ticker = 'PETR4';

-- Forçar coleta de novo período
DELETE FROM market.ohlcv WHERE ticker = 'PETR4' AND date >= '2024-11-01';
```

### Execução Muito Lenta

**Sintoma**: Crawler demora > 10 minutos

**Causas**:
1. **Muitos tickers**: Modo completo coleta centenas de ativos
2. **Rate limit**: Delays entre requests somam tempo
3. **Network lento**: Conexão lenta com Brapi ou PostgreSQL

**Otimizações**:
1. **Use modo sample**: `python app/main.py --sample`
2. **Paralelização**: Adicionar `asyncio` para requests paralelas
3. **Batch insert**: Inserir múltiplos registros de uma vez

### Cloud Run Job Timeout

**Sintoma**: Job termina antes de completar

**Solução**:
```bash
# Aumentar timeout do job (máximo: 3600s = 1h)
gcloud run jobs update crawler-brapi \
  --timeout=3600 \
  --region=us-central1
```

---

## 🔄 Agendamento

### Opção 1: Cloud Scheduler (GCP)

```bash
# Criar job que executa diariamente às 2h AM (horário de Brasília)
gcloud scheduler jobs create http crawler-brapi-daily \
  --location=us-central1 \
  --schedule="0 2 * * *" \
  --time-zone="America/Sao_Paulo" \
  --uri="https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/PROJECT_ID/jobs/crawler-brapi:run" \
  --http-method=POST \
  --oauth-service-account-email="SA@PROJECT_ID.iam.gserviceaccount.com"
```

### Opção 2: Cron (Linux/Mac)

```bash
# Editar crontab
crontab -e

# Adicionar linha (diariamente às 2h AM)
0 2 * * * cd /path/to/learning-llmops/pipelines/crawler-brapi && docker run --env-file .env crawler-brapi:latest >> /var/log/crawler.log 2>&1
```

**Sintaxe cron**:
```
┌───────────── minuto (0 - 59)
│ ┌───────────── hora (0 - 23)
│ │ ┌───────────── dia do mês (1 - 31)
│ │ │ ┌───────────── mês (1 - 12)
│ │ │ │ ┌───────────── dia da semana (0 - 6) (0 = domingo)
│ │ │ │ │
0 2 * * *
```

**Exemplos**:
```cron
# Todo dia às 2h AM
0 2 * * *

# A cada 6 horas
0 */6 * * *

# Segunda a sexta às 18h (após fechamento da bolsa)
0 18 * * 1-5

# Todo domingo às 3h AM (consolidação semanal)
0 3 * * 0
```

### Opção 3: Task Scheduler (Windows)

```powershell
# Criar tarefa agendada
$action = New-ScheduledTaskAction -Execute "docker" -Argument "run --env-file .env crawler-brapi:latest"
$trigger = New-ScheduledTaskTrigger -Daily -At 2am
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "CrawlerBrapi" -Description "Coleta diária de dados financeiros"
```

---

## 📚 Documentação Adicional

- **[DEPLOY.md](./DEPLOY.md)** - Deploy avançado em cloud (Cloud Run Job)
- **[Brapi API Docs](https://brapi.dev/docs)** - Documentação oficial da API
- **[Cloud Scheduler Docs](https://cloud.google.com/scheduler/docs)** - Agendamento no GCP
- **[Crontab Guru](https://crontab.guru/)** - Gerador de expressões cron

---

## 🤝 Contribuindo

Veja [CONTRIBUTING.md](../../CONTRIBUTING.md) na raiz do projeto.

---

**Desenvolvido com 📈 pelo Learning LLMOps Team**
