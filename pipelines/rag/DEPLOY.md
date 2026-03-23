# Deploy Avançado - RAG Pipeline

Este documento explica como fazer deploy do pipeline RAG no Google Cloud Platform, incluindo o **Vectorization Job** e a **Generation API**, com versionamento, CI/CD e rollback.

## Por que usar cloudbuild.yaml?

### 1. Versionamento de Imagens

Com `cloudbuild.yaml`, cada imagem é versionada no Artifact Registry:

```yaml
images:
  - '${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPOSITORY}/${_IMAGE_NAME}'
  - '${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPOSITORY}/${_IMAGE_NAME}:latest'
```

**Benefícios:**
- ✅ Histórico completo de versões
- ✅ Rollback fácil
- ✅ Rastreabilidade (qual commit → qual imagem)
- ✅ Reuso entre ambientes (dev, staging, prod)

### 2. CI/CD Integrado

Triggers automáticos executam build/deploy em cada push:

```bash
gcloud builds triggers create github \
  --name="rag-generation-api-deploy" \
  --repo-name="learning-llmops" \
  --branch-pattern="^main$" \
  --build-config="pipelines/rag/generation_api/cloudbuild.yaml"
```

**Fluxo:**
```
git push → Trigger → Build → Push → Deploy → Notificação
```

### 3. Builds Reproduzíveis

O `cloudbuild.yaml` documenta exatamente o processo de build:
- Qualquer pessoa pode reproduzir
- Histórico de mudanças no Git
- Auditoria de segurança
- Debugging facilitado

### 4. Integração GCP

Com imagens no Artifact Registry:
- **Cloud Scheduler**: Agendar job com imagem específica
- **Cloud Monitoring**: Rastrear métricas por versão
- **Multi-ambiente**: Usar mesma imagem em dev/staging/prod

## Comparação: Com vs Sem `cloudbuild.yaml`

### ❌ Sem `cloudbuild.yaml` (deploy.sh simples)

```bash
# deploy.sh antigo
gcloud builds submit --tag gcr.io/PROJECT/rag-api
gcloud run deploy rag-api --image gcr.io/PROJECT/rag-api
```

**Limitações:**
- Sem versionamento adequado
- Sem CI/CD automático
- Difícil fazer rollback
- Sem rastreabilidade
- Builds manuais apenas

### ✅ Com `cloudbuild.yaml` (atual)

```bash
# deploy.sh atual
gcloud builds submit --config=pipelines/rag/generation_api/cloudbuild.yaml .
```

**Vantagens:**
- ✅ Versionamento no Artifact Registry
- ✅ CI/CD com triggers
- ✅ Rollback fácil
- ✅ Rastreabilidade completa
- ✅ Builds automáticos e manuais

## Arquitetura de Deploy

```
┌─────────────────────────────────────────────────────────┐
│                    Git Repository                        │
│  (pipelines/rag/generation_api/cloudbuild.yaml)         │
└────────────────────┬────────────────────────────────────┘
                    │ git push
                    ↓
┌─────────────────────────────────────────────────────────┐
│              Cloud Build Trigger                        │
│  (opcional: automático em cada push)                   │
└────────────────────┬────────────────────────────────────┘
                    │
                    ↓
┌─────────────────────────────────────────────────────────┐
│              Cloud Build                                │
│  1. Build Docker image                                  │
│  2. Push para Artifact Registry                         │
│  3. Deploy no Cloud Run                                 │
└────────────────────┬────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        ↓                       ↓
┌──────────────────┐   ┌──────────────────┐
│ Artifact Registry│   │  Cloud Run       │
│ (versionamento)  │   │  (deploy)        │
└──────────────────┘   └──────────────────┘
```

## Casos de Uso

### Caso 1: Deploy Manual

```bash
# Executar deploy manualmente
cd pipelines/rag/generation_api
bash deploy.sh
```

**Quando usar:**
- Deploy inicial
- Testes locais
- Deploy de hotfix

### Caso 2: CI/CD Automático

```bash
# Criar trigger (uma vez)
gcloud builds triggers create github \
  --name="rag-api-auto-deploy" \
  --repo-name="learning-llmops" \
  --branch-pattern="^main$" \
  --build-config="pipelines/rag/generation_api/cloudbuild.yaml"
```

**Quando usar:**
- Deploy automático em produção
- Integração contínua
- Reduzir erros manuais

### Caso 3: Rollback

```bash
# Listar versões disponíveis
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/PROJECT/docker-images/rag-generation-api

# Fazer rollback para versão anterior
gcloud run services update rag-generation-api \
  --image=us-central1-docker.pkg.dev/PROJECT/docker-images/rag-generation-api@sha256:ABC123
```

**Quando usar:**
- Bug em produção
- Performance degradada
- Necessidade de voltar versão anterior

### Caso 4: Multi-ambiente

```bash
# Deploy em staging
gcloud builds submit \
  --config=pipelines/rag/generation_api/cloudbuild.yaml \
  --substitutions=_ENV=staging

# Deploy em produção
gcloud builds submit \
  --config=pipelines/rag/generation_api/cloudbuild.yaml \
  --substitutions=_ENV=production
```

**Quando usar:**
- Ambientes separados (dev/staging/prod)
- Testes antes de produção
- Validação de mudanças

## Estrutura dos Arquivos

```
pipelines/rag/
├── vectorization_job/
│   ├── cloudbuild.yaml      # Configuração de build/deploy do job
│   ├── deploy.sh            # Script de deploy (usa cloudbuild.yaml)
│   └── Dockerfile           # Imagem Docker do job
│
└── generation_api/
    ├── cloudbuild.yaml      # Configuração de build/deploy da API
    ├── deploy.sh            # Script de deploy (usa cloudbuild.yaml)
    └── Dockerfile           # Imagem Docker da API
```

## Comandos Úteis

### Verificar Builds

```bash
# Listar builds recentes
gcloud builds list --limit=10

# Ver detalhes de um build
gcloud builds describe BUILD_ID
```

### Verificar Imagens no Artifact Registry

```bash
# Listar imagens
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/PROJECT/docker-images/rag-generation-api

# Ver tags de uma imagem
gcloud artifacts docker tags list \
  us-central1-docker.pkg.dev/PROJECT/docker-images/rag-generation-api
```

### Verificar Deploy

```bash
# Status do serviço
gcloud run services describe rag-generation-api --region us-central1

# Logs do serviço
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=rag-generation-api" --limit=50
```

## Próximos Passos

1. **Criar triggers automáticos** para CI/CD
2. **Configurar notificações** (Slack, email) em caso de falha
3. **Implementar testes** antes do deploy
4. **Configurar staging** antes de produção
5. **Monitorar métricas** de deploy (tempo, taxa de sucesso)

## Referências

- [Cloud Build Documentation](https://cloud.google.com/build/docs)
- [Artifact Registry Documentation](https://cloud.google.com/artifact-registry/docs)
- [Cloud Run Jobs Documentation](https://cloud.google.com/run/docs/create-jobs)
- [Cloud Run Services Documentation](https://cloud.google.com/run/docs/deploy)
