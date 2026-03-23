# Deploy Avançado - Agents Pipeline

Este documento explica como fazer deploy do pipeline de agentes no Google Cloud Platform com versionamento, CI/CD e rollback.

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

Sem `cloudbuild.yaml`, imagens são construídas sem rastreabilidade:

```bash
# Deploy manual simples (SEM versionamento)
gcloud builds submit --tag gcr.io/PROJECT/agents
gcloud run deploy agents --image gcr.io/PROJECT/agents
```

**Problema**: Não há histórico de versões, difícil rollback, sem rastreabilidade.

Com `cloudbuild.yaml`, imagens são versionadas no Artifact Registry:

```yaml
images:
  - '${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPOSITORY}/${_IMAGE_NAME}'
  - '${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPOSITORY}/${_IMAGE_NAME}:latest'
```

**Benefícios**:
- ✅ Histórico completo de versões
- ✅ Rollback fácil
- ✅ Rastreabilidade (qual commit gerou qual imagem)
- ✅ Reuso entre ambientes (dev/staging/prod)

### 2. CI/CD Integrado

Triggers automáticos executam deploy em cada push:

```bash
# Criar trigger (uma vez)
gcloud builds triggers create github \
  --name="agents-auto-deploy" \
  --repo-name="learning-llmops" \
  --branch-pattern="^main$" \
  --build-config="pipelines/agents/cloudbuild.yaml"
```

**Fluxo**:
```
git push → Trigger → Build → Push → Deploy → Notificação
```

### 3. Builds Reproduzíveis

O `cloudbuild.yaml` documenta exatamente como construir a imagem:
- Qualquer pessoa pode reproduzir
- Histórico de mudanças no Git
- Auditoria de segurança
- Debugging facilitado

### 4. Integração GCP

Com imagens no Artifact Registry:
- **Cloud Scheduler**: Agendar execuções com imagem específica
- **Cloud Monitoring**: Rastrear métricas por versão
- **Cloud Logging**: Filtrar logs por versão
- **Multi-ambiente**: Usar mesma imagem em dev/staging/prod

---

## Arquitetura de Deploy

```
┌─────────────────────────────────────────────────────────┐
│                    Git Repository                        │
│  (pipelines/agents/cloudbuild.yaml)                     │
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
│ (versionamento)  │   │  (serviço)       │
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
echo -n "sua_senha" | gcloud secrets create DB_PASSWORD --data-file=-
```

### Deploy com deploy.sh

```bash
cd pipelines/agents
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
  --config=pipelines/agents/cloudbuild.yaml \
  --project=SEU_PROJECT_ID \
  --timeout=1200s \
  .

# Verificar serviço
gcloud run services describe agents \
  --region=us-central1 \
  --format='value(status.url)'
```

---

## CI/CD Automático

### 1. Criar Trigger no Cloud Build

```bash
# Trigger para branch main (produção)
gcloud builds triggers create github \
  --name="agents-prod-deploy" \
  --repo-name="learning-llmops" \
  --repo-owner="seu-usuario" \
  --branch-pattern="^main$" \
  --build-config="pipelines/agents/cloudbuild.yaml" \
  --description="Deploy automático de agents em produção"
```

### 2. Criar Trigger para Staging

```bash
# Trigger para branch develop (staging)
gcloud builds triggers create github \
  --name="agents-staging-deploy" \
  --repo-name="learning-llmops" \
  --repo-owner="seu-usuario" \
  --branch-pattern="^develop$" \
  --build-config="pipelines/agents/cloudbuild.yaml" \
  --substitutions=_ENV=staging,_SERVICE_NAME=agents-staging
```

### 3. Configurar Notificações

**Slack**:
```bash
# Criar notificador Slack
gcloud builds notifiers create slack-notifier \
  --webhook-url="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Associar ao trigger
gcloud builds triggers update agents-prod-deploy \
  --notifier-config=slack-notifier
```

**Email**:
```bash
# Via Cloud Monitoring
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
  us-central1-docker.pkg.dev/PROJECT/docker-images/agents

# Ver tags de uma imagem
gcloud artifacts docker tags list \
  us-central1-docker.pkg.dev/PROJECT/docker-images/agents
```

### Tagear Versões

```bash
# Tag manual (além de latest)
gcloud artifacts docker tags add \
  us-central1-docker.pkg.dev/PROJECT/docker-images/agents:latest \
  us-central1-docker.pkg.dev/PROJECT/docker-images/agents:v1.2.0
```

### Deploy de Versão Específica

```bash
# Deploy de versão v1.2.0
gcloud run services update agents \
  --image=us-central1-docker.pkg.dev/PROJECT/docker-images/agents:v1.2.0 \
  --region=us-central1
```

---

## Rollback

### Rollback Automático (Tráfego)

Cloud Run permite rollback gradual sem downtime:

```bash
# 1. Listar revisões
gcloud run revisions list --service=agents --region=us-central1

# 2. Dividir tráfego (canary)
gcloud run services update-traffic agents \
  --to-revisions=agents-00002-xyz=50,agents-00001-abc=50 \
  --region=us-central1

# 3. Rollback completo para revisão anterior
gcloud run services update-traffic agents \
  --to-revisions=agents-00001-abc=100 \
  --region=us-central1
```

### Rollback por Imagem

```bash
# 1. Listar versões de imagem
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/PROJECT/docker-images/agents

# 2. Deploy da versão anterior
gcloud run services update agents \
  --image=us-central1-docker.pkg.dev/PROJECT/docker-images/agents@sha256:ABC123... \
  --region=us-central1
```

### Rollback de Revisão

```bash
# Voltar para última revisão estável
LAST_STABLE=$(gcloud run revisions list \
  --service=agents \
  --region=us-central1 \
  --format='value(metadata.name)' \
  --limit=2 | tail -n 1)

gcloud run services update-traffic agents \
  --to-revisions=$LAST_STABLE=100 \
  --region=us-central1
```

---

## Multi-ambiente

### Estratégia Recomendada

```
┌──────────────────────────────────────────────────────────┐
│  Branch: develop  →  Cloud Run: agents-staging          │
│  Branch: main     →  Cloud Run: agents-production       │
└──────────────────────────────────────────────────────────┘
```

### Deploy Staging

**cloudbuild.staging.yaml**:
```yaml
substitutions:
  _IMAGE_NAME: agents-staging
  _SERVICE_ACCOUNT: agents-staging@${PROJECT_ID}.iam.gserviceaccount.com
  _ENV: staging

steps:
  # ... mesmos steps, diferentes substitutions
```

**Deploy**:
```bash
gcloud builds submit \
  --config=pipelines/agents/cloudbuild.staging.yaml \
  .
```

### Deploy Production

```bash
gcloud builds submit \
  --config=pipelines/agents/cloudbuild.yaml \
  .
```

### Variáveis por Ambiente

```bash
# Staging
gcloud run services update agents-staging \
  --set-env-vars="APP_ENV=staging,BUDGET_USD_DAY=5.0" \
  --region=us-central1

# Production
gcloud run services update agents \
  --set-env-vars="APP_ENV=production,BUDGET_USD_DAY=15.0" \
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
  "resource.type=cloud_run_revision AND resource.labels.service_name=agents" \
  --limit=50 \
  --format=json

# Logs de erro
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=agents AND severity>=ERROR" \
  --limit=20

# Logs de uma revisão específica
gcloud logging read \
  "resource.labels.revision_name=agents-00005-xyz" \
  --limit=50
```

### Métricas

```bash
# Requests por minuto
gcloud monitoring time-series list \
  --filter='metric.type="run.googleapis.com/request_count" AND resource.labels.service_name="agents"'

# Latência média
gcloud monitoring time-series list \
  --filter='metric.type="run.googleapis.com/request_latencies" AND resource.labels.service_name="agents"'

# CPU utilization
gcloud monitoring time-series list \
  --filter='metric.type="run.googleapis.com/container/cpu/utilizations" AND resource.labels.service_name="agents"'
```

---

## Troubleshooting Avançado

### Build Falhou

**Ver logs**:
```bash
gcloud builds list --limit=1 --format='value(id)'
gcloud builds log $(gcloud builds list --limit=1 --format='value(id)')
```

**Causas comuns**:
1. **Timeout**: Aumente `timeout` no cloudbuild.yaml
2. **Dependências**: Verifique `requirements.txt`
3. **Dockerfile**: Teste build local antes

### Deploy Falhou

**Ver status**:
```bash
gcloud run services describe agents --region=us-central1
```

**Causas comuns**:
1. **Secrets não configurados**: Configure no Secret Manager
2. **Service account sem permissões**: Adicione IAM roles
3. **Recursos insuficientes**: Aumente `--memory` ou `--cpu`

### Serviço Instável

**Ver revisões com problemas**:
```bash
gcloud run revisions list --service=agents --region=us-central1
```

**Ver logs de crash**:
```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND severity=ERROR" \
  --limit=50
```

**Health checks falhando**:
```bash
# Verificar endpoint /health
SERVICE_URL=$(gcloud run services describe agents --format='value(status.url)')
curl $SERVICE_URL/health -v
```

### Custo Alto

**Ver custos detalhados**:
```bash
# Console: Cloud Billing → Reports
# Filtrar por: Product = Cloud Run, Service = agents
```

**Otimizações**:
1. **Reduzir min-instances**: `--min-instances=0`
2. **Reduzir CPU**: `--cpu=0.5` (se possível)
3. **Reduzir memória**: `--memory=512Mi` (se possível)
4. **Aumentar concurrency**: `--concurrency=80`

---

## Comandos Úteis

### Informações do Serviço

```bash
# URL
gcloud run services describe agents --format='value(status.url)'

# Revisão atual
gcloud run services describe agents --format='value(status.latestCreatedRevisionName)'

# Tráfego por revisão
gcloud run services describe agents --format='value(status.traffic)'
```

### Atualizar Configuração

```bash
# Aumentar recursos
gcloud run services update agents \
  --memory=2Gi \
  --cpu=2 \
  --timeout=300s \
  --region=us-central1

# Atualizar variáveis
gcloud run services update agents \
  --set-env-vars="NEW_VAR=value" \
  --update-env-vars="EXISTING_VAR=new_value" \
  --remove-env-vars="OLD_VAR" \
  --region=us-central1

# Atualizar secrets
gcloud run services update agents \
  --set-secrets="OPENROUTER_API_KEY=OPENROUTER_API_KEY:latest" \
  --region=us-central1
```

### Deletar Recursos

```bash
# Deletar serviço (cuidado!)
gcloud run services delete agents --region=us-central1

# Deletar revisões antigas (manter últimas 10)
gcloud run revisions list --service=agents --region=us-central1 --format='value(metadata.name)' | tail -n +11 | xargs -I {} gcloud run revisions delete {} --region=us-central1 --quiet
```

---

## Checklist de Deploy

### Pré-Deploy
- [ ] Código testado localmente
- [ ] Testes unitários passando
- [ ] Variáveis de ambiente configuradas
- [ ] Secrets criados no Secret Manager
- [ ] Service account com permissões corretas
- [ ] Budget alerts configurados

### Durante Deploy
- [ ] Build bem-sucedido
- [ ] Push para Artifact Registry completo
- [ ] Deploy no Cloud Run completo
- [ ] Health check OK

### Pós-Deploy
- [ ] Teste endpoint `/health`
- [ ] Teste endpoint funcional (ex: `/generate_analysis`)
- [ ] Verificar logs (sem erros)
- [ ] Verificar métricas (latência, CPU, memória)
- [ ] Documentar URL no `.env`
- [ ] Notificar time

---

## Recursos

- [Cloud Build Documentation](https://cloud.google.com/build/docs)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Artifact Registry Documentation](https://cloud.google.com/artifact-registry/docs)
- [Best Practices for Cloud Run](https://cloud.google.com/run/docs/best-practices)

---

**Dúvidas?** Abra uma issue ou consulte a documentação oficial do GCP.
