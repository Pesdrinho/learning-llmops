# Deploy Avançado - API Blackbox

Este documento explica como fazer deploy da API Blackbox no Google Cloud Platform com versionamento, CI/CD e rollback.

---

## 📋 Índice

- [Por que usar cloudbuild.yaml?](#por-que-usar-cloudbuildyaml)
- [Arquitetura de Deploy](#arquitetura-de-deploy)
- [Deploy Manual](#deploy-manual)
- [CI/CD Automático](#cicd-automático)
- [Versionamento](#versionamento)
- [Rollback](#rollback)
- [Multi-ambiente](#multi-ambiente)
- [Monitoramento](#monitoramento)
- [Troubleshooting Avançado](#troubleshooting-avançado)

---

## Por que usar cloudbuild.yaml?

### 1. Versionamento Completo

Com `cloudbuild.yaml`, cada imagem é versionada no Artifact Registry:

```yaml
images:
  - '${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPOSITORY}/api-blackbox'
  - '${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPOSITORY}/api-blackbox:latest'
```

**Benefícios**:
- ✅ Histórico completo de versões
- ✅ Rollback fácil para qualquer versão anterior
- ✅ Rastreabilidade (saber qual commit gerou qual imagem)
- ✅ Reuso entre ambientes (dev/staging/prod)

### 2. CI/CD Integrado

Triggers automáticos executam deploy em cada push:

```bash
gcloud builds triggers create github \
  --name="api-blackbox-auto-deploy" \
  --repo-name="learning-llmops" \
  --branch-pattern="^main$" \
  --build-config="pipelines/api-blackbox/cloudbuild.yaml"
```

**Fluxo**:
```
git push → Trigger → Build → Push → Deploy → Notificação
```

### 3. Builds Reproduzíveis

O `cloudbuild.yaml` documenta exatamente o processo de build:
- Qualquer pessoa pode reproduzir
- Histórico de mudanças no Git
- Auditoria de segurança
- Debugging facilitado com logs centralizados

### 4. Integração GCP

Com imagens no Artifact Registry:
- **Cloud Monitoring**: Rastrear métricas por versão
- **Cloud Logging**: Filtrar logs por versão
- **Multi-ambiente**: Usar mesma imagem em dev/staging/prod
- **Rollback rápido**: Voltar versões em segundos

---

## Arquitetura de Deploy

```
┌─────────────────────────────────────────────────────────┐
│                    Git Repository                        │
│  (pipelines/api-blackbox/cloudbuild.yaml)               │
└────────────────────┬────────────────────────────────────┘
                    │ git push (opcional: trigger)
                    ↓
┌─────────────────────────────────────────────────────────┐
│              Cloud Build Trigger                        │
│  (opcional: automático em cada push)                   │
└────────────────────┬────────────────────────────────────┘
                    │
                    ↓
┌─────────────────────────────────────────────────────────┐
│              Cloud Build                                │
│  1. Build Docker image (Dockerfile.prod)                │
│  2. Push para Artifact Registry                         │
│  3. Deploy no Cloud Run                                 │
└────────────────────┬────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        ↓                       ↓
┌──────────────────┐   ┌──────────────────┐
│ Artifact Registry│   │  Cloud Run       │
│ (versionamento)  │   │  (API Gateway)   │
└──────────────────┘   └──────────────────┘
```

---

## Deploy Manual

### Pré-requisitos

```bash
# 1. Instale gcloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# 2. Autentique
gcloud auth login

# 3. Configure projeto
gcloud config set project SEU_PROJECT_ID

# 4. Configure secrets
echo -n "sk-or-v1-..." | gcloud secrets create OPENROUTER_API_KEY --data-file=-
echo -n "postgresql://..." | gcloud secrets create DATABASE_URL --data-file=-
```

### Deploy com deploy.sh

```bash
cd pipelines/api-blackbox
bash deploy.sh
```

O script:
1. ✅ Valida configuração e credenciais
2. ✅ Faz build via Cloud Build
3. ✅ Deploy no Cloud Run
4. ✅ Exibe URL e informações

### Deploy Manual Puro

```bash
# Build e deploy em um comando
gcloud builds submit \
  --config=pipelines/api-blackbox/cloudbuild.yaml \
  --project=SEU_PROJECT_ID \
  --timeout=1200s \
  .

# Verificar serviço
gcloud run services describe api-blackbox \
  --region=us-central1 \
  --format='value(status.url)'
```

---

## CI/CD Automático

### 1. Criar Trigger para Produção

```bash
gcloud builds triggers create github \
  --name="api-blackbox-prod-deploy" \
  --repo-name="learning-llmops" \
  --repo-owner="seu-usuario" \
  --branch-pattern="^main$" \
  --build-config="pipelines/api-blackbox/cloudbuild.yaml" \
  --description="Deploy automático de API Blackbox em produção"
```

### 2. Criar Trigger para Staging

```bash
gcloud builds triggers create github \
  --name="api-blackbox-staging-deploy" \
  --repo-name="learning-llmops" \
  --repo-owner="seu-usuario" \
  --branch-pattern="^develop$" \
  --build-config="pipelines/api-blackbox/cloudbuild.yaml" \
  --substitutions=_ENV=staging,_SERVICE_NAME=api-blackbox-staging
```

### 3. Configurar Notificações

**Slack**:
```bash
# Criar notificador Slack
gcloud builds notifiers create slack-notifier \
  --webhook-url="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Associar ao trigger
gcloud builds triggers update api-blackbox-prod-deploy \
  --notifier-config=slack-notifier
```

**Email via Cloud Monitoring**:
```bash
gcloud monitoring notification-channels create \
  --type=email \
  --display-name="Deploy Alerts" \
  --channel-labels=email_address=seu-email@example.com
```

---

## Versionamento

### Listar Versões Disponíveis

```bash
# Listar todas as imagens
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/PROJECT/docker-images/api-blackbox

# Ver tags e digests
gcloud artifacts docker tags list \
  us-central1-docker.pkg.dev/PROJECT/docker-images/api-blackbox
```

### Tagear Versões Semanticamente

```bash
# Tag manual com versão semântica
gcloud artifacts docker tags add \
  us-central1-docker.pkg.dev/PROJECT/docker-images/api-blackbox:latest \
  us-central1-docker.pkg.dev/PROJECT/docker-images/api-blackbox:v2.1.0
```

### Deploy de Versão Específica

```bash
# Deploy de versão v2.1.0
gcloud run services update api-blackbox \
  --image=us-central1-docker.pkg.dev/PROJECT/docker-images/api-blackbox:v2.1.0 \
  --region=us-central1
```

---

## Rollback

### Rollback Automático (Tráfego Gradual)

Cloud Run permite rollback sem downtime:

```bash
# 1. Listar revisões
gcloud run revisions list --service=api-blackbox --region=us-central1

# 2. Canary deployment (50/50)
gcloud run services update-traffic api-blackbox \
  --to-revisions=api-blackbox-00002-xyz=50,api-blackbox-00001-abc=50 \
  --region=us-central1

# 3. Rollback completo para revisão anterior
gcloud run services update-traffic api-blackbox \
  --to-revisions=api-blackbox-00001-abc=100 \
  --region=us-central1
```

### Rollback por Imagem (Digest)

```bash
# 1. Listar imagens com digest
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/PROJECT/docker-images/api-blackbox \
  --include-tags

# 2. Deploy da versão anterior usando digest
gcloud run services update api-blackbox \
  --image=us-central1-docker.pkg.dev/PROJECT/docker-images/api-blackbox@sha256:ABC123... \
  --region=us-central1
```

### Rollback Rápido (última revisão estável)

```bash
# Voltar para última revisão estável
LAST_STABLE=$(gcloud run revisions list \
  --service=api-blackbox \
  --region=us-central1 \
  --format='value(metadata.name)' \
  --limit=2 | tail -n 1)

gcloud run services update-traffic api-blackbox \
  --to-revisions=$LAST_STABLE=100 \
  --region=us-central1
```

---

## Multi-ambiente

### Estratégia Recomendada

```
┌──────────────────────────────────────────────────────────┐
│  Branch: develop  →  Cloud Run: api-blackbox-staging    │
│  Branch: main     →  Cloud Run: api-blackbox-prod       │
└──────────────────────────────────────────────────────────┘
```

### Deploy Staging

**cloudbuild.staging.yaml**:
```yaml
substitutions:
  _IMAGE_NAME: api-blackbox-staging
  _SERVICE_ACCOUNT: api-staging@${PROJECT_ID}.iam.gserviceaccount.com
  _ENV: staging

steps:
  # ... mesmos steps, diferentes substitutions
```

**Deploy**:
```bash
gcloud builds submit \
  --config=pipelines/api-blackbox/cloudbuild.staging.yaml \
  .
```

### Variáveis por Ambiente

```bash
# Staging (budget menor para testes)
gcloud run services update api-blackbox-staging \
  --set-env-vars="APP_ENV=staging,BUDGET_USD_DAY=5.0,LOG_LEVEL=DEBUG" \
  --region=us-central1

# Production (budget normal)
gcloud run services update api-blackbox \
  --set-env-vars="APP_ENV=production,BUDGET_USD_DAY=15.0,LOG_LEVEL=INFO" \
  --region=us-central1
```

---

## Monitoramento

### Logs de Build

```bash
# Listar builds recentes
gcloud builds list --limit=10

# Ver logs de um build específico
gcloud builds log BUILD_ID

# Stream de logs em tempo real
gcloud builds log BUILD_ID --stream
```

### Logs da Aplicação

```bash
# Logs recentes
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=api-blackbox" \
  --limit=50 \
  --format=json

# Logs de erro
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=api-blackbox AND severity>=ERROR" \
  --limit=20

# Logs de uma revisão específica
gcloud logging read \
  "resource.labels.revision_name=api-blackbox-00005-xyz" \
  --limit=50

# Logs de PII masking (verificar se está funcionando)
gcloud logging read \
  "resource.labels.service_name=api-blackbox AND textPayload=~'PII detected'" \
  --limit=20
```

### Métricas

```bash
# Requests por minuto
gcloud monitoring time-series list \
  --filter='metric.type="run.googleapis.com/request_count" AND resource.labels.service_name="api-blackbox"'

# Latência (P50, P95, P99)
gcloud monitoring time-series list \
  --filter='metric.type="run.googleapis.com/request_latencies" AND resource.labels.service_name="api-blackbox"'

# Taxa de erro (4xx, 5xx)
gcloud monitoring time-series list \
  --filter='metric.type="run.googleapis.com/request_count" AND resource.labels.service_name="api-blackbox" AND metric.label.response_code_class!="2xx"'

# Custo estimado (requests × custo médio)
gcloud logging read \
  "resource.labels.service_name=api-blackbox AND jsonPayload.cost_usd>0" \
  --limit=100 \
  --format="value(jsonPayload.cost_usd)"
```

### Alertas Personalizados

**Alerta de custo alto**:
```bash
# Criar alerta se custo diário > $20
gcloud monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="API Blackbox - Custo Alto" \
  --condition-display-name="Custo diário > $20" \
  --condition-threshold-value=20 \
  --condition-threshold-duration=600s
```

**Alerta de erro 5xx**:
```bash
# Criar alerta se taxa de erro 5xx > 5%
gcloud monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="API Blackbox - Alta Taxa de Erro" \
  --condition-display-name="Taxa de erro 5xx > 5%" \
  --condition-threshold-value=0.05 \
  --condition-threshold-duration=300s
```

---

## Troubleshooting Avançado

### Build Falhou

**Ver logs detalhados**:
```bash
BUILD_ID=$(gcloud builds list --limit=1 --format='value(id)')
gcloud builds log $BUILD_ID
```

**Causas comuns**:
1. **Timeout**: Aumente `timeout` no cloudbuild.yaml (padrão: 600s)
2. **Dependências faltando**: Verifique `requirements.txt`
3. **Dockerfile inválido**: Teste build local antes

**Teste local**:
```bash
docker build -f pipelines/api-blackbox/Dockerfile.prod -t api-blackbox:test .
docker run --rm -p 8080:8080 --env-file .env api-blackbox:test
```

### Deploy Falhou

**Ver status detalhado**:
```bash
gcloud run services describe api-blackbox \
  --region=us-central1 \
  --format=yaml
```

**Causas comuns**:
1. **Secrets não configurados**:
   ```bash
   gcloud secrets list
   gcloud secrets versions access latest --secret=OPENROUTER_API_KEY
   ```
2. **Service account sem permissões**:
   ```bash
   # Adicionar roles necessárias
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:SA_EMAIL" \
     --role="roles/cloudsql.client"
   ```
3. **Recursos insuficientes**: Aumente `--memory` ou `--cpu`

### Serviço com Alta Latência

**Identificar gargalos**:
```bash
# Ver latência por percentil
gcloud logging read \
  "resource.labels.service_name=api-blackbox AND jsonPayload.latency_ms>0" \
  --format="value(jsonPayload.latency_ms)" \
  --limit=100
```

**Otimizações**:
1. **Aumentar CPU**: `--cpu=2`
2. **Aumentar concorrência**: `--concurrency=80`
3. **Reduzir cold starts**: `--min-instances=1`
4. **Usar modelos mais rápidos**: `gpt-oss-120b` ao invés de `gpt-4`

### Budget Excedido Frequentemente

**Analisar padrões de uso**:
```sql
-- Conectar no PostgreSQL
SELECT
  DATE(ts) as dia,
  model,
  COUNT(*) as requests,
  SUM(cost_usd) as custo_total,
  AVG(cost_usd) as custo_medio
FROM observability.spend_ledger
WHERE ts >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE(ts), model
ORDER BY dia DESC, custo_total DESC;
```

**Soluções**:
1. **Aumentar budget**: `BUDGET_USD_DAY=30.0`
2. **Usar modelos mais baratos**: Priorize `gpt-oss-120b`
3. **Implementar rate limit por usuário**: Adicionar middleware
4. **Cache de respostas**: Implementar Redis para queries repetidas

### PII Vazando

**Verificar logs**:
```bash
# Buscar possíveis vazamentos (CPF, email não mascarados)
gcloud logging read \
  "resource.labels.service_name=api-blackbox AND textPayload=~'[0-9]{3}\\.[0-9]{3}\\.[0-9]{3}-[0-9]{2}'" \
  --limit=10
```

**Teste de mascaramento**:
```bash
# Testar via API
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Meu CPF é 123.456.789-00"}],
    "model": "gpt-oss-120b"
  }'

# Verificar logs para confirmar que foi mascarado
```

---

## Configuração Avançada

### Auto-scaling

```bash
# Configurar auto-scaling
gcloud run services update api-blackbox \
  --min-instances=1 \
  --max-instances=10 \
  --cpu-throttling \
  --region=us-central1
```

### Timeout e Recursos

```bash
# Aumentar timeout e recursos para modelos lentos
gcloud run services update api-blackbox \
  --timeout=300s \
  --memory=2Gi \
  --cpu=2 \
  --region=us-central1
```

### Concorrência

```bash
# Aumentar concorrência (mais requests por instância)
gcloud run services update api-blackbox \
  --concurrency=80 \
  --region=us-central1
```

### VPC Connector (acesso a Cloud SQL via IP privado)

```bash
# Criar VPC connector
gcloud compute networks vpc-access connectors create api-connector \
  --region=us-central1 \
  --range=10.8.0.0/28

# Associar ao serviço
gcloud run services update api-blackbox \
  --vpc-connector=api-connector \
  --vpc-egress=private-ranges-only \
  --region=us-central1
```

---

## Comandos Úteis

### Informações do Serviço

```bash
# URL
gcloud run services describe api-blackbox --format='value(status.url)'

# Revisão atual
gcloud run services describe api-blackbox --format='value(status.latestCreatedRevisionName)'

# Tráfego por revisão
gcloud run services describe api-blackbox --format='value(status.traffic)'
```

### Atualizar Configuração

```bash
# Atualizar variáveis de ambiente
gcloud run services update api-blackbox \
  --set-env-vars="BUDGET_USD_DAY=20.0" \
  --update-env-vars="LOG_LEVEL=DEBUG" \
  --region=us-central1

# Atualizar secrets
gcloud run services update api-blackbox \
  --set-secrets="OPENROUTER_API_KEY=OPENROUTER_API_KEY:latest" \
  --region=us-central1
```

### Deletar Recursos

```bash
# Deletar serviço
gcloud run services delete api-blackbox --region=us-central1

# Deletar revisões antigas (manter últimas 10)
gcloud run revisions list \
  --service=api-blackbox \
  --region=us-central1 \
  --format='value(metadata.name)' \
  | tail -n +11 \
  | xargs -I {} gcloud run revisions delete {} --region=us-central1 --quiet
```

---

## Checklist de Deploy

### Pré-Deploy
- [ ] Código testado localmente
- [ ] Testes unitários passando
- [ ] Secrets configurados no Secret Manager
- [ ] Service account com permissões corretas
- [ ] Budget alerts configurados
- [ ] PII masking testado

### Durante Deploy
- [ ] Build bem-sucedido
- [ ] Push para Artifact Registry completo
- [ ] Deploy no Cloud Run completo
- [ ] Health check OK

### Pós-Deploy
- [ ] Teste `/health`
- [ ] Teste `/chat` com dados sensíveis (verificar mascaramento)
- [ ] Teste `/models`
- [ ] Verificar logs (sem erros)
- [ ] Verificar métricas (latência, custo)
- [ ] Testar rate limit (exceder budget)
- [ ] Documentar URL no `.env`

---

## Recursos

- [Cloud Build Documentation](https://cloud.google.com/build/docs)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Artifact Registry Documentation](https://cloud.google.com/artifact-registry/docs)
- [OpenRouter API Docs](https://openrouter.ai/docs)
- [Best Practices for Cloud Run](https://cloud.google.com/run/docs/best-practices)

---

**Dúvidas?** Abra uma issue ou consulte a documentação oficial.
