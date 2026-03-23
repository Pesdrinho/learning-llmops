#!/bin/bash

#
# Script de Deploy - API Blackbox para Cloud Run
#
# Este script automatiza o processo de deploy:
# 1. Valida configuração
# 2. Faz build da imagem
# 3. Deploy no Cloud Run
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

set -e  # Para execução se algum comando falhar

# ========== CORES PARA OUTPUT ==========

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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
echo -e "${GREEN}🚀 Deploy API Blackbox - Cloud Run${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# ========== CARREGA VARIÁVEIS DO .ENV ==========

# Encontra raiz do projeto
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

log_info "Raiz do projeto: $PROJECT_ROOT"

# Carrega .env
if [ -f "$PROJECT_ROOT/.env" ]; then
    log_success "Carregando variáveis do .env..."

    # Parser seguro que ignora comentários e linhas vazias
    while IFS= read -r line || [ -n "$line" ]; do
        # Remove espaços
        line=$(echo "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')

        # Ignora linhas vazias e comentários
        if [ -z "$line" ] || [[ "$line" =~ ^# ]]; then
            continue
        fi

        # Exporta variável se formato válido
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

# Verifica GCP_PROJECT_ID
if [ -z "$GCP_PROJECT_ID" ]; then
    log_error "GCP_PROJECT_ID não configurado no .env"
    exit 1
fi

log_success "GCP_PROJECT_ID: $GCP_PROJECT_ID"

# Verifica gcloud CLI
if ! command -v gcloud &> /dev/null; then
    log_error "gcloud CLI não encontrado. Instale: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

log_success "gcloud CLI encontrado"

# Verifica autenticação
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
SERVICE_NAME="api-blackbox"
REPOSITORY="docker-images"

log_info "Configuração do deploy:"
echo -e "  ${YELLOW}Projeto:${NC} $PROJECT_ID"
echo -e "  ${YELLOW}Região:${NC} $REGION"
echo -e "  ${YELLOW}Serviço:${NC} $SERVICE_NAME"
echo -e "  ${YELLOW}Repository:${NC} $REPOSITORY"
echo ""

# Configura projeto padrão
gcloud config set project $PROJECT_ID

# ========== CONFIRMAÇÃO ==========

log_warning "Isso irá:"
echo "  1. Fazer build da imagem Docker"
echo "  2. Push para Artifact Registry"
echo "  3. Deploy no Cloud Run (pode sobrescrever versão existente)"
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
echo ""

# Submit build
# --timeout: Timeout de 20 minutos
# --suppress-logs: Não exibe logs completos (muito verbose)
gcloud builds submit \
    --config=pipelines/api-blackbox/cloudbuild.yaml \
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
echo ""

# Espera serviço ficar pronto
sleep 5

# Verifica se serviço existe
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

# URL do serviço
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
    --platform=managed \
    --region=$REGION \
    --format='value(status.url)')

# Revisão atual
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
echo "2. Teste o endpoint de chat:"
echo -e "   ${BLUE}curl -X POST $SERVICE_URL/chat \\${NC}"
echo -e "   ${BLUE}  -H 'Content-Type: application/json' \\${NC}"
echo -e "   ${BLUE}  -H 'Authorization: Bearer YOUR_API_KEY' \\${NC}"
echo -e "   ${BLUE}  -d '{${NC}"
echo -e "   ${BLUE}    \"messages\": [{\"role\": \"user\", \"content\": \"Olá!\"}],${NC}"
echo -e "   ${BLUE}    \"model\": \"gpt-oss-120b\"${NC}"
echo -e "   ${BLUE}  }'${NC}"
echo ""
echo "3. Configure secrets (se ainda não fez):"
echo -e "   ${BLUE}gcloud secrets create OPENROUTER_API_KEY --data-file=- <<< 'sk-or-v1-xxx'${NC}"
echo -e "   ${BLUE}gcloud secrets create DATABASE_URL --data-file=- <<< 'postgresql://...'${NC}"
echo ""
echo "   Depois, atualize o cloudbuild.yaml para usar os secrets"
echo ""
echo "4. Visualize logs:"
echo -e "   ${BLUE}gcloud logging read \"resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME\" --limit=50${NC}"
echo ""
echo "5. Documente a URL no seu .env:"
echo -e "   ${BLUE}API_BLACKBOX_URL=$SERVICE_URL${NC}"
echo ""

echo -e "${GREEN}Deploy finalizado! 🎊${NC}"
echo ""
