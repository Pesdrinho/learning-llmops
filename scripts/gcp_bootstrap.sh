#!/bin/bash

# Script de Bootstrap GCP para LLMOps Lab
# Cria recursos necessários no Google Cloud Platform

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Função para log
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Carrega variáveis do .env
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    log_error "Arquivo .env não encontrado. Copie env.example para .env e configure."
    exit 1
fi

# Verifica variáveis obrigatórias
if [ -z "$GCP_PROJECT_ID" ]; then
    log_error "GCP_PROJECT_ID não configurado no .env"
    exit 1
fi

REGION=${GCP_REGION:-us-central1}

log_info "Configurando projeto: $GCP_PROJECT_ID"
log_info "Região: $REGION"
echo ""

# Configura projeto padrão
gcloud config set project $GCP_PROJECT_ID

# 1. Habilita APIs necessárias
log_info "Habilitando APIs necessárias..."
gcloud services enable \
    sqladmin.googleapis.com \
    run.googleapis.com \
    storage.googleapis.com \
    secretmanager.googleapis.com \
    cloudscheduler.googleapis.com \
    cloudbuild.googleapis.com \
    compute.googleapis.com

echo ""
log_info "APIs habilitadas com sucesso!"
echo ""

# 2. Cria instância Cloud SQL (se não existir)
DB_INSTANCE=${DB_INSTANCE_NAME:-llmops-db}
log_info "Verificando instância Cloud SQL: $DB_INSTANCE"

if gcloud sql instances describe $DB_INSTANCE --project=$GCP_PROJECT_ID 2>/dev/null; then
    log_warn "Instância Cloud SQL já existe: $DB_INSTANCE"
else
    log_info "Criando instância Cloud SQL PostgreSQL 15..."
    gcloud sql instances create $DB_INSTANCE \
        --database-version=POSTGRES_15 \
        --tier=db-f1-micro \
        --region=$REGION \
        --storage-type=SSD \
        --storage-size=10GB \
        --storage-auto-increase \
        --backup-start-time=03:00 \
        --maintenance-window-day=SUN \
        --maintenance-window-hour=4

    log_info "Aguardando instância ficar pronta..."
    sleep 30

    # Habilita pgvector
    log_info "Habilitando extensão pgvector..."
    gcloud sql databases create ${DB_NAME:-llmops} --instance=$DB_INSTANCE

    # Cria usuário
    log_info "Criando usuário do banco..."
    gcloud sql users create ${DB_USER:-llmops_user} \
        --instance=$DB_INSTANCE \
        --password=${DB_PASSWORD:-change_me_in_production}

    log_info "Instância Cloud SQL criada com sucesso!"
fi

# Anota connection name
DB_CONNECTION_NAME="$GCP_PROJECT_ID:$REGION:$DB_INSTANCE"
log_info "DB_CONNECTION_NAME: $DB_CONNECTION_NAME"
echo ""

# 3. Cria buckets Cloud Storage
log_info "Criando buckets Cloud Storage..."

BUCKET_DOCS=${GCS_RAG_DOCS_BUCKET:-llmops-rag-docs-$GCP_PROJECT_ID}
BUCKET_DATASETS=${GCS_DATASETS_BUCKET:-llmops-datasets-$GCP_PROJECT_ID}

for BUCKET in $BUCKET_DOCS $BUCKET_DATASETS; do
    if gsutil ls -b gs://$BUCKET 2>/dev/null; then
        log_warn "Bucket já existe: $BUCKET"
    else
        log_info "Criando bucket: $BUCKET"
        gsutil mb -l $REGION -c STANDARD gs://$BUCKET
        # Configura lifecycle (opcional)
        echo '[{"action": {"type": "Delete"}, "condition": {"age": 365}}]' | \
            gsutil lifecycle set /dev/stdin gs://$BUCKET
    fi
done

echo ""

# 4. Configura Secret Manager
log_info "Configurando Secret Manager..."

create_secret() {
    local SECRET_NAME=$1
    local SECRET_VALUE=$2

    if gcloud secrets describe $SECRET_NAME --project=$GCP_PROJECT_ID 2>/dev/null; then
        log_warn "Secret já existe: $SECRET_NAME"
    else
        if [ -n "$SECRET_VALUE" ]; then
            log_info "Criando secret: $SECRET_NAME"
            echo -n "$SECRET_VALUE" | gcloud secrets create $SECRET_NAME --data-file=-
        else
            log_warn "Valor vazio para $SECRET_NAME, pulando criação"
        fi
    fi
}

create_secret "BRAPI_TOKEN" "$BRAPI_TOKEN"
create_secret "OPENROUTER_API_KEY" "$OPENROUTER_API_KEY"
create_secret "OPENAI_API_KEY" "$OPENAI_API_KEY"
create_secret "LANGSMITH_API_KEY" "$LANGSMITH_API_KEY"
create_secret "DB_PASSWORD" "${DB_PASSWORD:-change_me_in_production}"

echo ""

# 5. Cria Service Account para Cloud Run
SA_NAME="llmops-runner"
SA_EMAIL="$SA_NAME@$GCP_PROJECT_ID.iam.gserviceaccount.com"

log_info "Verificando Service Account: $SA_NAME"

if gcloud iam service-accounts describe $SA_EMAIL --project=$GCP_PROJECT_ID 2>/dev/null; then
    log_warn "Service Account já existe: $SA_EMAIL"
else
    log_info "Criando Service Account..."
    gcloud iam service-accounts create $SA_NAME \
        --display-name="LLMOps Cloud Run Service Account" \
        --project=$GCP_PROJECT_ID
fi

# Concede permissões
log_info "Configurando permissões do Service Account..."

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/cloudsql.client" \
    --condition=None

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/storage.objectAdmin" \
    --condition=None

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None

echo ""
log_info "Service Account configurado!"

# 6. Resumo
echo ""
echo "========================================="
log_info "Bootstrap GCP Completo!"
echo "========================================="
echo ""
echo "Anote as seguintes informações no seu .env:"
echo ""
echo "GCP_PROJECT_ID=$GCP_PROJECT_ID"
echo "GCP_REGION=$REGION"
echo "DB_CONNECTION_NAME=$DB_CONNECTION_NAME"
echo "GCS_RAG_DOCS_BUCKET=$BUCKET_DOCS"
echo "GCS_DATASETS_BUCKET=$BUCKET_DATASETS"
echo "SERVICE_ACCOUNT_EMAIL=$SA_EMAIL"
echo ""
echo "Próximos passos:"
echo "1. Atualize o arquivo .env com as informações acima"
echo "2. Execute: bash scripts/apply_ddls.py para criar schemas"
echo "3. Execute: make seed para carregar dados iniciais"
echo ""
log_info "Ambiente GCP pronto para uso!"
