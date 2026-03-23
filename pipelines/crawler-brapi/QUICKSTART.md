# Quickstart - Crawler Brapi

## 🎉 Deploy Concluído com Sucesso!

Seu crawler está rodando em:
**https://crawler-brapi-opb3altjaq-uc.a.run.app**

---

## 📡 Endpoints Disponíveis

### 1. Health Check
```bash
curl https://crawler-brapi-opb3altjaq-uc.a.run.app/
# Resposta: {"status":"healthy","service":"crawler-brapi","version":"1.0.0"}
```

### 2. Health Check Detalhado
```bash
curl https://crawler-brapi-opb3altjaq-uc.a.run.app/health
# Resposta: {"status":"healthy","service":"crawler-brapi","environment":"production"}
```

### 3. Executar Crawler (Modo Sample - Teste)
```bash
curl -X POST https://crawler-brapi-opb3altjaq-uc.a.run.app/run/sample
```

Coleta apenas alguns tickers para teste rápido.

### 4. Executar Crawler (Modo Full - Produção)
```bash
curl -X POST https://crawler-brapi-opb3altjaq-uc.a.run.app/run/full
```

Coleta todos os dados disponíveis (pode demorar vários minutos).

### 5. Executar Crawler (Customizado)
```bash
curl -X POST "https://crawler-brapi-opb3altjaq-uc.a.run.app/run?sample=true"
curl -X POST "https://crawler-brapi-opb3altjaq-uc.a.run.app/run?sample=false"
```

---

## 🔄 Fazer Novo Deploy

### Opção 1: Via gcloud (Recomendado)
```bash
gcloud builds submit \
  --config=pipelines/crawler-brapi/cloudbuild.yaml \
  --project=llmops-473913 \
  .
```

### Opção 2: Via Script Bash
```bash
bash pipelines/crawler-brapi/deploy.sh
```

---

## 📅 Agendar Execução Diária

Criar job no Cloud Scheduler para executar o crawler automaticamente:

```bash
# Obter URL do serviço
SERVICE_URL=$(gcloud run services describe crawler-brapi \
  --region=us-central1 \
  --project=llmops-473913 \
  --format='value(status.url)')

# Criar agendamento (diariamente à meia-noite)
gcloud scheduler jobs create http crawler-brapi-daily \
  --schedule='0 0 * * *' \
  --uri="${SERVICE_URL}/run/full" \
  --http-method=POST \
  --oidc-service-account-email=learning-llmops@llmops-473913.iam.gserviceaccount.com \
  --location=us-central1 \
  --project=llmops-473913
```

### Outros Agendamentos Úteis

```bash
# A cada 6 horas
--schedule='0 */6 * * *'

# Segunda a Sexta às 9h
--schedule='0 9 * * 1-5'

# Todo domingo à meia-noite
--schedule='0 0 * * 0'
```

---

## 📊 Monitoramento

### Ver Logs em Tempo Real
```bash
gcloud run services logs tail crawler-brapi \
  --region=us-central1 \
  --project=llmops-473913
```

### Ver Últimos Logs
```bash
gcloud run services logs read crawler-brapi \
  --region=us-central1 \
  --limit=100 \
  --project=llmops-473913
```

### Ver Métricas no Console
```
https://console.cloud.google.com/run/detail/us-central1/crawler-brapi/metrics?project=llmops-473913
```

---

## 🛠 Desenvolvimento Local

### 1. Instalar Dependências
```bash
cd pipelines/crawler-brapi
pip install -r requirements.txt
```

### 2. Configurar .env
```bash
cp ../../env.example ../../.env
# Editar .env com suas credenciais
```

### 3. Executar Servidor Localmente
```bash
cd app
uvicorn server:app --reload --port 8080
```

### 4. Testar Localmente
```bash
# Health check
curl http://localhost:8080/health

# Executar crawler (sample)
curl -X POST http://localhost:8080/run/sample

# Ver documentação Swagger
open http://localhost:8080/docs
```

---

## 🐛 Troubleshooting

### Serviço não responde
```bash
# Verificar status
gcloud run services describe crawler-brapi \
  --region=us-central1 \
  --project=llmops-473913

# Ver logs de erro
gcloud run services logs read crawler-brapi \
  --region=us-central1 \
  --limit=50 \
  --project=llmops-473913
```

### Erro 403 Forbidden
```bash
# Permitir acesso público
gcloud run services add-iam-policy-binding crawler-brapi \
  --region=us-central1 \
  --member="allUsers" \
  --role="roles/run.invoker" \
  --project=llmops-473913
```

### Ver Revisões Deployadas
```bash
gcloud run revisions list \
  --service=crawler-brapi \
  --region=us-central1 \
  --project=llmops-473913
```

### Rollback para Revisão Anterior
```bash
# Listar revisões
gcloud run revisions list --service=crawler-brapi --region=us-central1

# Fazer rollback
gcloud run services update-traffic crawler-brapi \
  --to-revisions=REVISION_NAME=100 \
  --region=us-central1 \
  --project=llmops-473913
```

---

## 📝 Arquivos Importantes

- `app/server.py` - Servidor FastAPI principal
- `app/main.py` - Lógica do crawler
- `requirements.txt` - Dependências Python
- `Dockerfile.prod` - Configuração do container
- `cloudbuild.yaml` - Pipeline de CI/CD
- `deploy.sh` - Script de deploy

---

## 💰 Custos Estimados

- **Cloud Run**: ~$0.01/dia (execução diária)
- **Cloud Build**: Gratuito (120 min/dia inclusos)
- **Artifact Registry**: ~$0.10/mês (armazenamento)
- **Cloud Scheduler**: ~$0.10/mês (1 job)

**Total estimado**: < $5/mês

---

## 🎯 Próximos Passos

1. ✅ Deploy funcionando
2. ⬜ Configurar Cloud Scheduler para execução automática
3. ⬜ Adicionar alertas no Cloud Monitoring
4. ⬜ Configurar VPC Connector para Cloud SQL privado
5. ⬜ Adicionar secrets via Secret Manager
6. ⬜ Implementar retry policy para falhas
7. ⬜ Adicionar testes automatizados

---

## 📚 Documentação Adicional

- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - Problemas e soluções detalhadas
- [DEPLOY.md](./DEPLOY.md) - Guia completo de deploy
- [README.md](./README.md) - Documentação do projeto

