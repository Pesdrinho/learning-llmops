# Deploy do Crawler Brapi - Cloud Run

## Visão Geral

O Crawler Brapi foi configurado como um **serviço HTTP** no Cloud Run que pode ser acionado via requisições HTTP.

## Arquitetura

```
Cloud Run (HTTP Server)
├── GET  /          → Health check
├── GET  /health    → Health check detalhado  
├── POST /run       → Executa crawler (query param: ?sample=true)
├── POST /run/sample → Executa modo sample
└── POST /run/full   → Executa modo full
```

## Deploy

### 1. Via Script PowerShell (Windows)

```powershell
# Execute o deploy
.\pipelines\crawler-brapi\deploy.ps1
```

### 2. Via gcloud CLI

```bash
gcloud builds submit \
  --config=pipelines/crawler-brapi/cloudbuild.yaml \
  --project=llmops-473913 \
  .
```

## Executando o Crawler

### Após o Deploy

```bash
# Obtém a URL do serviço
SERVICE_URL=$(gcloud run services describe crawler-brapi \
  --region=us-central1 \
  --format='value(status.url)')

# Executa em modo sample (teste)
curl -X POST "$SERVICE_URL/run/sample"

# Executa em modo full (produção)
curl -X POST "$SERVICE_URL/run/full"

# Health check
curl "$SERVICE_URL/health"
```

### Agendamento com Cloud Scheduler

Para executar diariamente:

```bash
# Cria job de agendamento
gcloud scheduler jobs create http crawler-brapi-daily \
  --schedule='0 0 * * *' \
  --uri='https://crawler-brapi-xxxxx.run.app/run/full' \
  --http-method=POST \
  --oidc-service-account-email=learning-llmops@llmops-473913.iam.gserviceaccount.com \
  --location=us-central1
```

## Desenvolvimento Local

### Testar localmente

```bash
cd pipelines/crawler-brapi/app

# Instalar dependências
pip install -r ../requirements.txt

# Executar servidor
uvicorn server:app --reload --port 8080
```

### Endpoints Locais

- http://localhost:8080/ - Health check
- http://localhost:8080/health - Status detalhado
- http://localhost:8080/docs - Swagger UI
- http://localhost:8080/run/sample - Executa sample

## Configuração de Ambiente

### Variáveis Necessárias

```env
# GCP
GCP_PROJECT_ID=llmops-473913
GCP_REGION=us-central1

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=llmops
DB_USER=llmops_user
DB_PASSWORD=***

# API
BRAPI_TOKEN=***

# App
APP_ENV=production
LOG_LEVEL=INFO
```

### Secrets no Cloud Run

Os secrets são configurados via Secret Manager:

```bash
# Criar secrets
echo -n "seu_token_aqui" | gcloud secrets create BRAPI_TOKEN \
  --data-file=- \
  --project=llmops-473913

echo -n "sua_senha_aqui" | gcloud secrets create DB_PASSWORD \
  --data-file=- \
  --project=llmops-473913
```

## Monitoramento

### Logs

```bash
# Ver logs do Cloud Run
gcloud run services logs read crawler-brapi \
  --region=us-central1 \
  --limit=50

# Seguir logs em tempo real
gcloud run services logs tail crawler-brapi \
  --region=us-central1
```

### Métricas

Acesse o Cloud Console:
- Cloud Run > crawler-brapi > Métricas
- Cloud Run > crawler-brapi > Logs

## Troubleshooting

### Container não inicia

```bash
# Verificar logs
gcloud run services logs read crawler-brapi --region=us-central1 --limit=100

# Verificar revisão atual
gcloud run revisions list --service=crawler-brapi --region=us-central1
```

### Timeout

Se o crawler demorar muito, aumente o timeout:

```yaml
# Em cloudbuild.yaml
- '--timeout=900'  # 15 minutos
```

### Erro de permissão

Verifique as permissões da service account:

```bash
gcloud projects get-iam-policy llmops-473913 \
  --flatten="bindings[].members" \
  --filter="bindings.members:learning-llmops@llmops-473913.iam.gserviceaccount.com"
```

## Custos

- **Cloud Run**: Pay-per-use (requests + CPU time)
- **Cloud Build**: ~$0.003/build-minute (primeiros 120 min/dia grátis)
- **Artifact Registry**: ~$0.10/GB/mês

Execução diária estimada: < $1/mês

