# Troubleshooting - Crawler Brapi Deploy

## Resumo da Jornada de Deploy

Este documento resume todos os problemas encontrados e soluções aplicadas durante o deploy do Crawler Brapi no Cloud Run.

## Problemas Encontrados e Soluções

### 1. ❌ Erro: Parser do .env com `export $(cat .env | xargs)`

**Erro:**
```bash
export: `CONTRIBUTING.md': not a valid identifier
export: `data-schemas': not a valid identifier
```

**Causa:** O comando estava tentando exportar nomes de arquivos ao invés de variáveis.

**Solução:**
```bash
# Em deploy.sh
set -a
source .env
set +a
```

---

### 2. ❌ Erro: arquivo .env não encontrado

**Erro:**
```bash
source: .env: file not found
```

**Causa:** Script estava procurando .env no diretório errado.

**Solução:**
```bash
# Detectar raiz do projeto automaticamente
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$PROJECT_ROOT/.env"
```

---

### 3. ❌ Erro: variável `$SHORT_SHA` vazia no cloudbuild.yaml

**Erro:**
```
invalid image name "...:": could not parse reference
```

**Causa:** Variável `$SHORT_SHA` não estava disponível.

**Solução:**
```yaml
# Usar $COMMIT_SHA ao invés de $SHORT_SHA
substitutions:
  _IMAGE_NAME: crawler-brapi
  _REGION: us-central1

'--image=${_REGION}-docker.pkg.dev/$PROJECT_ID/docker-images/${_IMAGE_NAME}:$COMMIT_SHA'
```

---

### 4. ❌ Erro: Permissões IAM insuficientes

**Erro:**
```
Permission 'iam.serviceaccounts.actAs' denied on service account
```

**Causa:** Cloud Build não tinha permissão para "agir como" a service account.

**Solução:**
```bash
# Dar permissão para Cloud Build usar a service account
gcloud iam service-accounts add-iam-policy-binding \
  learning-llmops@llmops-473913.iam.gserviceaccount.com \
  --member=serviceAccount:253948405085-compute@developer.gserviceaccount.com \
  --role=roles/iam.serviceAccountUser

# Dar permissões para a service account
gcloud projects add-iam-policy-binding llmops-473913 \
  --member=serviceAccount:learning-llmops@llmops-473913.iam.gserviceaccount.com \
  --role=roles/run.admin

gcloud projects add-iam-policy-binding llmops-473913 \
  --member=serviceAccount:learning-llmops@llmops-473913.iam.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor

gcloud projects add-iam-policy-binding llmops-473913 \
  --member=serviceAccount:learning-llmops@llmops-473913.iam.gserviceaccount.com \
  --role=roles/cloudsql.client
```

---

### 5. ❌ Erro: Conflito de dependências (langgraph)

**Erro:**
```
ERROR: Cannot install learning-llmops==0.1.0
The conflict is caused by: learning-llmops 0.1.0 depends on langgraph==0.6.0
```

**Causa:** Dockerfile instalava TODAS as dependências do projeto, incluindo pacotes pesados desnecessários.

**Solução:**
Criar `requirements.txt` específico com apenas dependências essenciais:
```txt
# Apenas o necessário para o crawler
fastapi==0.119.0
uvicorn[standard]==0.37.0
sqlalchemy==2.0.44
asyncpg==0.30.0
httpx==0.28.1
# ... etc
```

Atualizar Dockerfile:
```dockerfile
COPY pipelines/crawler-brapi/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
```

---

### 6. ❌ Erro: Container não inicia na porta 8080

**Erro:**
```
The user-provided container failed to start and listen on the port defined by PORT=8080
```

**Causa:** Arquivo `main.py` era um script que executava e terminava, não um servidor HTTP.

**Solução:**
Criar servidor FastAPI (`server.py`):
```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "healthy"}

@app.post("/run")
async def run_crawler():
    await run_full_crawl()
    return {"status": "success"}
```

Atualizar Dockerfile:
```dockerfile
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

### 7. ❌ Erro: ModuleNotFoundError no import

**Erro:**
```python
File "/app/pipelines/crawler-brapi/app/main.py", line 16
from app.brapi_client import get_brapi_client
ModuleNotFoundError: No module named 'app'
```

**Causa:** Imports relativos incorretos após mudar WORKDIR.

**Solução:**
Ajustar imports em `main.py`:
```python
# ❌ ANTES
from app.brapi_client import get_brapi_client
from app.extractors import crypto

# ✅ DEPOIS
from brapi_client import get_brapi_client
from extractors import crypto
```

---

## ✅ Deploy Final Bem-Sucedido

Após resolver todos os problemas acima, o deploy funcionou perfeitamente!

**Logs de Sucesso:**
```
INFO: Started server process [1]
INFO: Waiting for application startup.
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:8080
```

**Teste:**
```bash
curl https://crawler-brapi-opb3altjaq-uc.a.run.app/health
# {"status":"healthy","service":"crawler-brapi","environment":"production"}
```

---

## Estrutura Final

```
pipelines/crawler-brapi/
├── app/
│   ├── server.py          # ✅ Servidor FastAPI
│   ├── server_minimal.py  # ✅ Servidor de teste
│   ├── main.py            # ✅ Lógica do crawler (imports corrigidos)
│   ├── brapi_client.py
│   ├── extractors/
│   └── loaders.py
├── requirements.txt       # ✅ Dependências mínimas
├── Dockerfile.prod        # ✅ Configurado corretamente
├── cloudbuild.yaml        # ✅ Substitutions corretas
└── deploy.sh              # ✅ Parser de .env corrigido
```

---

## Comandos Úteis para Debug

### Ver logs em tempo real
```bash
gcloud run services logs tail crawler-brapi \
  --region=us-central1 \
  --project=llmops-473913
```

### Ver revisões deployadas
```bash
gcloud run revisions list \
  --service=crawler-brapi \
  --region=us-central1 \
  --project=llmops-473913
```

### Testar localmente
```bash
cd pipelines/crawler-brapi/app
uvicorn server:app --reload --port 8080
```

### Verificar permissões
```bash
gcloud projects get-iam-policy llmops-473913 \
  --flatten="bindings[].members" \
  --filter="bindings.members:learning-llmops@"
```

---

## Lições Aprendidas

1. **Sempre começar simples**: Criar servidor minimal primeiro para isolar problemas
2. **Logs são essenciais**: Usar `gcloud run services logs read` para debug
3. **Imports relativos**: Cuidado com WORKDIR e estrutura de imports
4. **Dependências mínimas**: Não incluir tudo, apenas o necessário
5. **Permissões IAM**: Service accounts precisam de múltiplas roles
6. **Testar incrementalmente**: Deploy → Ver logs → Ajustar → Repeat

---

## Checklist para Novos Deploys

- [ ] .env no root do projeto
- [ ] requirements.txt atualizado
- [ ] Imports relativos corretos
- [ ] Service account com permissões necessárias
- [ ] Artifact Registry criado
- [ ] Servidor HTTP escutando na porta 8080
- [ ] Health check endpoint funcionando
- [ ] Testar localmente antes do deploy
- [ ] Verificar logs após deploy

