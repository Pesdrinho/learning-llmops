#!/bin/bash

#
# Script de Deploy - RAG Generation API para Cloud Run
#
# Este script automatiza o processo de deploy:
# 1. Valida configuração
# 2. Faz build da imagem via Cloud Build
# 3. Deploy no Cloud Run Service
# 4. Exibe informações do serviço
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
echo -e "${GREEN}🌐 Deploy RAG Generation API${NC}"
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
SERVICE_NAME="rag-generation-api"
REPOSITORY="docker-images"

log_info "Configuração do deploy:"
echo -e "  ${YELLOW}Projeto:${NC} $PROJECT_ID"
echo -e "  ${YELLOW}Região:${NC} $REGION"
echo -e "  ${YELLOW}Serviço:${NC} $SERVICE_NAME"
echo -e "  ${YELLOW}Repository:${NC} $REPOSITORY"
echo ""

gcloud config set project $PROJECT_ID

# ========== CONFIRMAÇÃO ==========

log_warning "Isso irá:"
echo "  1. Fazer build da imagem Docker via Cloud Build"
echo "  2. Push para Artifact Registry (versionamento)"
echo "  3. Deploy no Cloud Run Service (pode sobrescrever versão existente)"
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
    --config=pipelines/rag/generation_api/cloudbuild.yaml \
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

if ! gcloud run services describe $SERVICE_NAME \
    --platform=managed \
    --region=$REGION \
    --format="value(status.url)" &> /dev/null; then
    log_error "Serviço não encontrado após deploy!"
    exit 1
fi

log_success "Serviço deployado com sucesso!"

# ========== INFORMAÇÕES DO SERVIÇO ==========

log_info "[3/3] Coletando informações do serviço..."
echo ""

SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
    --platform=managed \
    --region=$REGION \
    --format='value(status.url)')

LATEST_REVISION=$(gcloud run services describe $SERVICE_NAME \
    --platform=managed \
    --region=$REGION \
    --format='value(status.latestCreatedRevisionName)')

# ========== SUCESSO! ==========

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 Deploy Completo!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}📍 Informações do Serviço:${NC}"
echo ""
echo -e "  ${BLUE}URL:${NC}"
echo -e "    $SERVICE_URL"
echo ""
echo -e "  ${BLUE}Revisão:${NC}"
echo -e "    $LATEST_REVISION"
echo ""
echo -e "  ${BLUE}Console GCP:${NC}"
echo -e "    https://console.cloud.google.com/run/detail/$REGION/$SERVICE_NAME"
echo ""

# ========== PRÓXIMOS PASSOS ==========

echo -e "${YELLOW}🚀 Próximos Passos:${NC}"
echo ""
echo "1. Teste a API:"
echo -e "   ${BLUE}curl $SERVICE_URL/health${NC}"
echo ""
echo "2. Faça uma query RAG:"
echo -e "   ${BLUE}curl -X POST $SERVICE_URL/query \\${NC}"
echo -e "   ${BLUE}  -H 'Content-Type: application/json' \\${NC}"
echo -e "   ${BLUE}  -d '{\"query\": \"Qual foi o último dividendo pago pela Petrobras?\"}'${NC}"
echo ""
echo "3. Visualize logs:"
echo -e "   ${BLUE}gcloud logging read \"resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME\" --limit=50${NC}"
echo ""
echo "4. Verifique imagens no Artifact Registry:"
echo -e "   ${BLUE}gcloud artifacts docker images list $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/rag-generation-api${NC}"
echo ""
echo "5. Documente a URL no seu .env:"
echo -e "   ${BLUE}RAG_GENERATION_API_URL=$SERVICE_URL${NC}"
echo ""

echo -e "${GREEN}Deploy finalizado! 🎊${NC}"
echo ""
