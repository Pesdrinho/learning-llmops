#!/bin/bash

#
# Script de Deploy - RAG Vectorization Job para Cloud Run
#
# Este script automatiza o processo de deploy:
# 1. Valida configuração
# 2. Faz build da imagem via Cloud Build
# 3. Deploy no Cloud Run Job
# 4. Exibe informações do job
#
# Uso:
#   bash deploy.sh
#
# Pré-requisitos:
#   - gcloud CLI instalado
#   - Autenticado: gcloud auth login
#   - Projeto configurado: gcloud config set project PROJECT_ID
#   - .env com GCP_PROJECT_ID
#

set -e

# ========== CORES PARA OUTPUT ==========

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# ========== FUNÇÕES HELPER ==========

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# ========== BANNER ==========

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}📊 Deploy RAG Vectorization Job${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# ========== CARREGA VARIÁVEIS DO .ENV ==========

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

log_info "Raiz do projeto: $PROJECT_ROOT"

if [ -f "$PROJECT_ROOT/.env" ]; then
    log_success "Carregando variáveis do .env..."

    while IFS= read -r line || [ -n "$line" ]; do
        line=$(echo "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')

        if [ -z "$line" ] || [[ "$line" =~ ^# ]]; then
            continue
        fi

        if [[ "$line" =~ ^[a-zA-Z_][a-zA-Z0-9_]*= ]]; then
            export "$line"
        fi
    done < "$PROJECT_ROOT/.env"

    log_success "Variáveis carregadas"
else
    log_warning "Arquivo .env não encontrado em $PROJECT_ROOT"
fi

echo ""

# ========== VALIDAÇÃO ==========

log_info "Validando configuração..."

if [ -z "$GCP_PROJECT_ID" ]; then
    log_error "GCP_PROJECT_ID não configurado no .env"
    exit 1
fi

log_success "GCP_PROJECT_ID: $GCP_PROJECT_ID"

if ! command -v gcloud &> /dev/null; then
    log_error "gcloud CLI não encontrado. Instale: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

log_success "gcloud CLI encontrado"

if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    log_error "Não autenticado no gcloud. Execute: gcloud auth login"
    exit 1
fi

ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)")
log_success "Autenticado como: $ACTIVE_ACCOUNT"

echo ""

# ========== CONFIGURAÇÃO ==========

PROJECT_ID=$GCP_PROJECT_ID
REGION=${GCP_REGION:-us-central1}
JOB_NAME="rag-vectorization-job"
REPOSITORY="docker-images"

log_info "Configuração do deploy:"
echo -e "  ${YELLOW}Projeto:${NC} $PROJECT_ID"
echo -e "  ${YELLOW}Região:${NC} $REGION"
echo -e "  ${YELLOW}Job:${NC} $JOB_NAME"
echo -e "  ${YELLOW}Repository:${NC} $REPOSITORY"
echo ""

gcloud config set project $PROJECT_ID

# ========== CONFIRMAÇÃO ==========

log_warning "Isso irá:"
echo "  1. Fazer build da imagem Docker via Cloud Build"
echo "  2. Push para Artifact Registry (versionamento)"
echo "  3. Deploy no Cloud Run Job (pode sobrescrever versão existente)"
echo ""

read -p "$(echo -e ${YELLOW}Continuar com o deploy? \(y/n\) ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Deploy cancelado"
    exit 0
fi

echo ""

# ========== BUILD E DEPLOY ==========

log_info "[1/3] Submetendo build para Cloud Build..."

gcloud builds submit \
    --config=pipelines/rag/vectorization_job/cloudbuild.yaml \
    --project=$PROJECT_ID \
    --timeout=1200s \
    --service-account="projects/${PROJECT_ID}/serviceAccounts/learning-llmops@${PROJECT_ID}.iam.gserviceaccount.com" \
    . || {
        log_error "Build falhou!"
        exit 1
    }

echo ""
log_success "Build completo!"

# ========== VERIFICAÇÃO ==========

log_info "[2/3] Verificando deploy..."

sleep 5

if ! gcloud run jobs describe $JOB_NAME \
    --region=$REGION \
    --format="value(name)" &> /dev/null; then
    log_error "Job não encontrado após deploy!"
    exit 1
fi

log_success "Job deployado com sucesso!"

# ========== INFORMAÇÕES DO JOB ==========

log_info "[3/3] Coletando informações do job..."
echo ""

LATEST_EXECUTION=$(gcloud run jobs executions list \
    --job=$JOB_NAME \
    --region=$REGION \
    --limit=1 \
    --format='value(name)' 2>/dev/null || echo "Nenhuma execução ainda")

# ========== SUCESSO! ==========

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 Deploy Completo!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}📍 Informações do Job:${NC}"
echo ""
echo -e "  ${BLUE}Nome:${NC}"
echo -e "    $JOB_NAME"
echo ""
echo -e "  ${BLUE}Última execução:${NC}"
echo -e "    $LATEST_EXECUTION"
echo ""
echo -e "  ${BLUE}Console GCP:${NC}"
echo -e "    https://console.cloud.google.com/run/jobs/detail/$REGION/$JOB_NAME"
echo ""

# ========== PRÓXIMOS PASSOS ==========

echo -e "${YELLOW}🚀 Próximos Passos:${NC}"
echo ""
echo "1. Executar o job manualmente:"
echo -e "   ${BLUE}gcloud run jobs execute $JOB_NAME --region $REGION${NC}"
echo ""
echo "2. Agendar execução (Cloud Scheduler):"
echo -e "   ${BLUE}gcloud scheduler jobs create http rag-vectorization-daily \\${NC}"
echo -e "   ${BLUE}  --location $REGION \\${NC}"
echo -e "   ${BLUE}  --schedule \"0 2 * * *\" \\${NC}"
echo -e "   ${BLUE}  --http-method POST \\${NC}"
echo -e "   ${BLUE}  --uri \"https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/$JOB_NAME:run\"${NC}"
echo ""
echo "3. Visualizar logs:"
echo -e "   ${BLUE}gcloud logging read \"resource.type=cloud_run_job AND resource.labels.job_name=$JOB_NAME\" --limit=50${NC}"
echo ""
echo "4. Verificar imagens no Artifact Registry:"
echo -e "   ${BLUE}gcloud artifacts docker images list $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/rag-vectorization-job${NC}"
echo ""

echo -e "${GREEN}Deploy finalizado! 🎊${NC}"
echo ""
