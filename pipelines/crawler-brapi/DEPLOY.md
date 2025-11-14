# Deploy Avançado - Crawler Brapi

Este documento explica como fazer deploy do Crawler Brapi no Google Cloud Platform como **Cloud Run Job** (não Service) com versionamento, CI/CD e agendamento.

---

## 📋 Índice

- [Cloud Run Job vs Service](#cloud-run-job-vs-service)
- [Por que usar cloudbuild.yaml?](#por-que-usar-cloudbuildyaml)
- [Arquitetura de Deploy](#arquitetura-de-deploy)
- [Deploy Manual](#deploy-manual)
- [Agendamento com Cloud Scheduler](#agendamento-com-cloud-scheduler)
- [CI/CD Automático](#cicd-automático)
- [Versionamento](#versionamento)
- [Rollback](#rollback)
- [Monitoramento](#monitoramento)
- [Troubleshooting Avançado](#troubleshooting-avançado)

---

## Cloud Run Job vs Service

### Diferenças Fundamentais

| Aspecto | Cloud Run **Job** | Cloud Run **Service** |
|---------|-------------------|----------------------|
| **Ciclo de vida** | Executa e termina | Fica rodando continuamente |
| **Ideal para** | Crawlers, ETL, batch | APIs, webhooks, servidores |
| **Endpoint HTTP** | Não expõe endpoint | Expõe URL pública |
| **Execução** | Sob demanda ou agendada | Responde a requests HTTP |
| **Timeout** | Até 24h | Até 60min por request |
| **Billing** | Paga apenas quando executa | Paga por instância ativa + requests |

### Por que Crawler é um Job?

✅ **Executa e termina**: Coleta dados e finaliza
✅ **Agendável**: Execução diária via Cloud Scheduler
✅ **Sem endpoint HTTP**: Não precisa responder requests
✅ **Long-running**: Pode demorar > 5min (coleta completa)

---

## Por que usar cloudbuild.yaml?

### 1. Versionamento Completo

Com `cloudbuild.yaml`, imagens são versionadas no Artifact Registry:

```yaml
images:
  - '${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPOSITORY}/crawler-brapi'
  - '${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPOSITORY}/crawler-brapi:latest'
```

**Benefícios**:
- ✅ Histórico de versões
- ✅ Rollback fácil
- ✅ Rastreabilidade (qual commit → qual imagem)
- ✅ Reuso entre ambientes

### 2. CI/CD Integrado

Triggers automáticos executam build/deploy em cada push:

```bash
gcloud builds triggers create github \
  --name="crawler-brapi-auto-deploy" \
  --repo-name="learning-llmops" \
  --branch-pattern="^main$" \
  --build-config="pipelines/crawler-brapi/cloudbuild.yaml"
```

### 3. Deploy Consistente

Mesma imagem para múltiplos ambientes:
- **Dev**: Teste manual
- **Staging**: Agendamento semanal
- **Prod**: Agendamento diário

---

## Arquitetura de Deploy

```
┌─────────────────────────────────────────────────────────┐
│                    Git Repository                        │
│  (pipelines/crawler-brapi/cloudbuild.yaml)              │
└────────────────────┬────────────────────────────────────┘
                    │ git push (opcional: trigger)
                    ↓
┌─────────────────────────────────────────────────────────┐
│              Cloud Build                                │
│  1. Build Docker image (Dockerfile.prod)                │
│  2. Push para Artifact Registry                         │
│  3. Deploy como Cloud Run Job                           │
└────────────────────┬────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        ↓                       ↓
┌──────────────────┐   ┌──────────────────┐
│ Artifact Registry│   │  Cloud Run Job   │
│ (versionamento)  │   │  (execução)      │
└──────────────────┘   └────────┬─────────┘
                                │
                                ↓
                       ┌────────────────────┐
                       │ Cloud Scheduler    │
                       │ (agendamento)      │
                       └────────────────────┘
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
echo -n "postgresql://..." | gcloud secrets create DATABASE_URL --data-file=-
echo -n "seu_token" | gcloud secrets create BRAPI_TOKEN --data-file=-  # Opcional
```

### Deploy com deploy.sh

```bash
cd pipelines/crawler-brapi
bash deploy.sh
```

O script:
1. ✅ Valida configuração
2. ✅ Build via Cloud Build
3. ✅ Deploy como Cloud Run Job
4. ✅ Testa execução

### Deploy Manual Puro

```bash
# Build e deploy
gcloud builds submit \
  --config=pipelines/crawler-brapi/cloudbuild.yaml \
  --project=SEU_PROJECT_ID \
  --timeout=1200s \
  .

# Executar job manualmente
gcloud run jobs execute crawler-brapi \
  --region=us-central1 \
  --wait
```

### Verificar Job

```bash
# Listar execuções
gcloud run jobs executions list \
  --job=crawler-brapi \
  --region=us-central1

# Ver logs da última execução
gcloud run jobs executions describe EXECUTION_NAME \
  --region=us-central1
```

---

## Agendamento com Cloud Scheduler

### Criar Agendamento Diário

```bash
# Executar diariamente às 2h AM (horário de Brasília)
gcloud scheduler jobs create http crawler-brapi-daily \
  --location=us-central1 \
  --schedule="0 2 * * *" \
  --time-zone="America/Sao_Paulo" \
  --uri="https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/PROJECT_ID/jobs/crawler-brapi:run" \
  --http-method=POST \
  --oauth-service-account-email="crawler-sa@PROJECT_ID.iam.gserviceaccount.com" \
  --description="Coleta diária de dados financeiros da Brapi"
```

### Outras Frequências

**A cada 6 horas**:
```bash
--schedule="0 */6 * * *"
```

**Segunda a sexta às 18h** (após fechamento da bolsa):
```bash
--schedule="0 18 * * 1-5"
```

**Semanalmente** (domingos às 3h AM):
```bash
--schedule="0 3 * * 0"
```

### Gerenciar Agendamento

```bash
# Listar agendamentos
gcloud scheduler jobs list --location=us-central1

# Pausar agendamento
gcloud scheduler jobs pause crawler-brapi-daily --location=us-central1

# Retomar agendamento
gcloud scheduler jobs resume crawler-brapi-daily --location=us-central1

# Deletar agendamento
gcloud scheduler jobs delete crawler-brapi-daily --location=us-central1
```

### Executar Manualmente (fora do agendamento)

```bash
# Trigger manual via Cloud Scheduler
gcloud scheduler jobs run crawler-brapi-daily --location=us-central1

# Ou executar job diretamente
gcloud run jobs execute crawler-brapi --region=us-central1 --wait
```

---

## CI/CD Automático

### 1. Criar Trigger para Produção

```bash
gcloud builds triggers create github \
  --name="crawler-brapi-prod-deploy" \
  --repo-name="learning-llmops" \
  --repo-owner="seu-usuario" \
  --branch-pattern="^main$" \
  --build-config="pipelines/crawler-brapi/cloudbuild.yaml" \
  --description="Deploy automático do Crawler Brapi"
```

### 2. Trigger para Teste (sem agendamento)

```bash
gcloud builds triggers create github \
  --name="crawler-brapi-test-deploy" \
  --repo-name="learning-llmops" \
  --repo-owner="seu-usuario" \
  --branch-pattern="^develop$" \
  --build-config="pipelines/crawler-brapi/cloudbuild.yaml" \
  --substitutions=_JOB_NAME=crawler-brapi-test
```

### 3. Notificações

**Slack**:
```bash
# Criar notificador
gcloud builds notifiers create slack-notifier \
  --webhook-url="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Associar ao trigger
gcloud builds triggers update crawler-brapi-prod-deploy \
  --notifier-config=slack-notifier
```

---

## Versionamento

### Listar Versões

```bash
# Listar imagens no Artifact Registry
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/PROJECT/docker-images/crawler-brapi

# Ver tags
gcloud artifacts docker tags list \
  us-central1-docker.pkg.dev/PROJECT/docker-images/crawler-brapi
```

### Tagear Versões

```bash
# Adicionar tag semântica
gcloud artifacts docker tags add \
  us-central1-docker.pkg.dev/PROJECT/docker-images/crawler-brapi:latest \
  us-central1-docker.pkg.dev/PROJECT/docker-images/crawler-brapi:v1.2.0
```

### Atualizar Job para Versão Específica

```bash
# Usar versão v1.2.0
gcloud run jobs update crawler-brapi \
  --image=us-central1-docker.pkg.dev/PROJECT/docker-images/crawler-brapi:v1.2.0 \
  --region=us-central1
```

---

## Rollback

### Rollback para Versão Anterior

```bash
# 1. Listar versões
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/PROJECT/docker-images/crawler-brapi

# 2. Atualizar job com digest da versão anterior
gcloud run jobs update crawler-brapi \
  --image=us-central1-docker.pkg.dev/PROJECT/docker-images/crawler-brapi@sha256:ABC123... \
  --region=us-central1

# 3. Testar execução
gcloud run jobs execute crawler-brapi --region=us-central1 --wait
```

### Rollback Rápido (última versão estável)

```bash
# Voltar para tag 'stable'
gcloud run jobs update crawler-brapi \
  --image=us-central1-docker.pkg.dev/PROJECT/docker-images/crawler-brapi:stable \
  --region=us-central1
```

**Estratégia recomendada**:
1. Sempre mantenha tag `stable` na última versão que funcionou
2. Antes de deploy, teste em job separado (ex: `crawler-brapi-test`)
3. Se novo deploy funcionar, atualize tag `stable`

```bash
# Após validar nova versão
gcloud artifacts docker tags add \
  us-central1-docker.pkg.dev/PROJECT/docker-images/crawler-brapi:latest \
  us-central1-docker.pkg.dev/PROJECT/docker-images/crawler-brapi:stable
```

---

## Monitoramento

### Logs de Execução

```bash
# Listar execuções
gcloud run jobs executions list \
  --job=crawler-brapi \
  --region=us-central1 \
  --limit=10

# Ver logs de uma execução específica
EXECUTION_NAME=$(gcloud run jobs executions list \
  --job=crawler-brapi \
  --region=us-central1 \
  --limit=1 \
  --format='value(metadata.name)')

gcloud logging read \
  "resource.labels.job_name=crawler-brapi AND resource.labels.execution_name=$EXECUTION_NAME" \
  --limit=100
```

### Logs em Tempo Real

```bash
# Durante execução, stream logs
gcloud run jobs execute crawler-brapi \
  --region=us-central1 \
  --async

# Em outro terminal, seguir logs
gcloud logging read \
  "resource.labels.job_name=crawler-brapi" \
  --limit=50 \
  --format=json \
  --freshness=1m
```

### Métricas

```bash
# Taxa de sucesso
gcloud logging read \
  "resource.type=cloud_run_job AND resource.labels.job_name=crawler-brapi" \
  --format="value(jsonPayload.status)" \
  --limit=100

# Duração de execuções
gcloud logging read \
  "resource.labels.job_name=crawler-brapi AND jsonPayload.duration_ms>0" \
  --format="value(jsonPayload.duration_ms)" \
  --limit=50
```

### Alertas

**Alerta de falha**:
```bash
# Criar alerta se job falhar 2x consecutivas
gcloud monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="Crawler Brapi - Falhas Consecutivas" \
  --condition-display-name="2 falhas consecutivas" \
  --condition-threshold-value=2 \
  --condition-threshold-duration=300s
```

**Alerta de timeout**:
```bash
# Criar alerta se execução > 30min
gcloud monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="Crawler Brapi - Timeout" \
  --condition-display-name="Duração > 30min" \
  --condition-threshold-value=1800 \
  --condition-threshold-duration=60s
```

---

## Troubleshooting Avançado

### Job Falha Imediatamente

**Sintoma**: Job termina em < 10s com erro

**Ver erro**:
```bash
EXECUTION_NAME=$(gcloud run jobs executions list \
  --job=crawler-brapi \
  --limit=1 \
  --format='value(metadata.name)')

gcloud logging read \
  "resource.labels.execution_name=$EXECUTION_NAME AND severity>=ERROR" \
  --limit=20
```

**Causas comuns**:
1. **Secrets não configurados**: Verifique `DATABASE_URL`
2. **Service account sem permissões**: Adicione roles necessárias
3. **Código com bug**: Teste localmente antes

### Job Timeout

**Sintoma**: Job termina após X minutos sem completar

**Aumentar timeout**:
```bash
# Aumentar para 60min (máximo padrão)
gcloud run jobs update crawler-brapi \
  --timeout=3600 \
  --region=us-central1

# Para timeout > 60min, use --max-retries com tarefas menores
gcloud run jobs update crawler-brapi \
  --max-retries=3 \
  --region=us-central1
```

**Otimizar crawler**:
1. Usar modo `--sample` para testes
2. Paralelizar requests com `asyncio`
3. Dividir em múltiplos jobs (ex: `crawler-ohlcv`, `crawler-dividends`)

### Job Executa Mas Não Insere Dados

**Verificar logs**:
```bash
# Buscar mensagens de sucesso/erro
gcloud logging read \
  "resource.labels.job_name=crawler-brapi AND textPayload=~'INSERT\|UPDATE\|ERROR'" \
  --limit=50
```

**Verificar banco**:
```bash
# Conectar e verificar
psql $DATABASE_URL -c "SELECT COUNT(*), MAX(updated_at) FROM market.ohlcv"
```

**Causas comuns**:
1. **Fim de semana**: Bolsa fechada, sem novos dados
2. **Upsert funcionando**: Dados já existem (esperado!)
3. **Erro de conexão**: Verifique firewall/VPC

### Cloud Scheduler Não Dispara

**Verificar agendamento**:
```bash
# Ver detalhes do job agendado
gcloud scheduler jobs describe crawler-brapi-daily --location=us-central1

# Verificar se está pausado
gcloud scheduler jobs describe crawler-brapi-daily \
  --location=us-central1 \
  --format='value(state)'
```

**Ver histórico de execuções**:
```bash
# Últimas 10 execuções
gcloud logging read \
  "resource.type=cloud_scheduler_job AND resource.labels.job_id=crawler-brapi-daily" \
  --limit=10
```

**Testar manualmente**:
```bash
# Trigger manual
gcloud scheduler jobs run crawler-brapi-daily --location=us-central1
```

### Custo Alto

**Ver custos**:
```bash
# Console: Cloud Billing → Reports
# Filtrar por: Product = Cloud Run, Job = crawler-brapi
```

**Otimizações**:
1. **Reduzir frequência**: Diário → Semanal
2. **Reduzir recursos**: `--memory=512Mi --cpu=0.5`
3. **Modo sample**: Coletar menos tickers
4. **Compartilhar infra**: Usar Cloud Run Service existente

---

## Configurações Avançadas

### Recursos

```bash
# Aumentar recursos para crawler completo
gcloud run jobs update crawler-brapi \
  --memory=2Gi \
  --cpu=2 \
  --region=us-central1
```

### Paralelismo

```bash
# Executar múltiplas tasks em paralelo
gcloud run jobs update crawler-brapi \
  --parallelism=5 \
  --region=us-central1
```

**Nota**: Requer adaptação do código para dividir trabalho entre tasks.

### Variáveis de Ambiente

```bash
# Adicionar/atualizar variáveis
gcloud run jobs update crawler-brapi \
  --set-env-vars="BRAPI_TOKEN=new_token,MODE=sample" \
  --region=us-central1

# Usar secrets
gcloud run jobs update crawler-brapi \
  --set-secrets="DATABASE_URL=DATABASE_URL:latest,BRAPI_TOKEN=BRAPI_TOKEN:latest" \
  --region=us-central1
```

### VPC Connector (acesso privado a Cloud SQL)

```bash
# Criar VPC connector
gcloud compute networks vpc-access connectors create crawler-connector \
  --region=us-central1 \
  --range=10.8.0.0/28

# Associar ao job
gcloud run jobs update crawler-brapi \
  --vpc-connector=crawler-connector \
  --vpc-egress=private-ranges-only \
  --region=us-central1
```

---

## Comandos Úteis

### Informações do Job

```bash
# Detalhes
gcloud run jobs describe crawler-brapi --region=us-central1

# Última execução
gcloud run jobs executions list \
  --job=crawler-brapi \
  --region=us-central1 \
  --limit=1

# Status da última execução
gcloud run jobs executions describe EXECUTION_NAME \
  --region=us-central1 \
  --format='value(status.completionTime,status.failureMessage)'
```

### Atualizar Job

```bash
# Atualizar imagem
gcloud run jobs update crawler-brapi \
  --image=us-central1-docker.pkg.dev/PROJECT/docker-images/crawler-brapi:v2.0.0 \
  --region=us-central1

# Atualizar timeout
gcloud run jobs update crawler-brapi \
  --timeout=3600 \
  --region=us-central1
```

### Deletar Recursos

```bash
# Deletar job (cuidado!)
gcloud run jobs delete crawler-brapi --region=us-central1

# Deletar agendamento
gcloud scheduler jobs delete crawler-brapi-daily --location=us-central1

# Limpar execuções antigas (automático após 30 dias)
```

---

## Checklist de Deploy

### Pré-Deploy
- [ ] Código testado localmente
- [ ] Schemas SQL aplicados no banco
- [ ] Secrets configurados (DATABASE_URL, BRAPI_TOKEN)
- [ ] Service account com permissões corretas
- [ ] Teste com `--sample` bem-sucedido

### Durante Deploy
- [ ] Build bem-sucedido
- [ ] Push para Artifact Registry completo
- [ ] Job criado no Cloud Run
- [ ] Execução manual bem-sucedida

### Pós-Deploy
- [ ] Agendamento criado no Cloud Scheduler
- [ ] Teste de execução agendada
- [ ] Verificar dados no banco (SELECT COUNT(*))
- [ ] Configurar alertas de falha
- [ ] Documentar última execução bem-sucedida

---

## Recursos

- [Cloud Run Jobs Documentation](https://cloud.google.com/run/docs/create-jobs)
- [Cloud Scheduler Documentation](https://cloud.google.com/scheduler/docs)
- [Artifact Registry Documentation](https://cloud.google.com/artifact-registry/docs)
- [Brapi API Documentation](https://brapi.dev/docs)

---

**Dúvidas?** Abra uma issue ou consulte a documentação oficial.
