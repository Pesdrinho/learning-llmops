#!/bin/bash

# Script de Deploy do Crawler Brapi para Cloud Run

set -e

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deploy Crawler Brapi - Cloud Run${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Encontra a raiz do projeto (diretório que contém o .env)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Carrega variáveis do .env se existir
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${GREEN}Carregando variáveis do .env...${NC}"
    # Parser seguro que ignora comentários, linhas vazias e exporta apenas KEY=VALUE válidos
    while IFS= read -r line || [ -n "$line" ]; do
        # Remove espaços em branco no início e fim
        line=$(echo "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
        
        # Ignora linhas vazias e comentários
        if [ -z "$line" ] || [[ "$line" =~ ^# ]]; then
            continue
        fi
        
        # Verifica se a linha está no formato KEY=VALUE
        if [[ "$line" =~ ^[a-zA-Z_][a-zA-Z0-9_]*= ]]; then
            export "$line"
        fi
    done < "$PROJECT_ROOT/.env"
    echo -e "${GREEN}Variáveis carregadas com sucesso${NC}"
    echo ""
else
    echo -e "${RED}Aviso: arquivo .env não encontrado em $PROJECT_ROOT${NC}"
    echo ""
fi

# Verifica variáveis obrigatórias
if [ -z "$GCP_PROJECT_ID" ]; then
    echo -e "${RED}Erro: GCP_PROJECT_ID não configurado no .env${NC}"
    exit 1
fi

PROJECT_ID=$GCP_PROJECT_ID
REGION=${GCP_REGION:-us-central1}
SERVICE_NAME="crawler-brapi"

echo -e "${YELLOW}Projeto:${NC} $PROJECT_ID"
echo -e "${YELLOW}Região:${NC} $REGION"
echo -e "${YELLOW}Serviço:${NC} $SERVICE_NAME"
echo ""

# Configura projeto padrão
gcloud config set project $PROJECT_ID

# Pergunta confirmação
read -p "Continuar com o deploy? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Deploy cancelado${NC}"
    exit 0
fi

echo ""
echo -e "${GREEN}[1/3] Submetendo build para Cloud Build...${NC}"

# Submit build
gcloud builds submit \
    --config=pipelines/crawler-brapi/cloudbuild.yaml \
    --project=$PROJECT_ID \
    --timeout=12000s \
    .

echo ""
echo -e "${GREEN}[2/3] Verificando deploy...${NC}"

# Espera serviço ficar pronto
sleep 5

# Obtém URL do serviço
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
    --platform=managed \
    --region=$REGION \
    --format='value(status.url)')

echo ""
echo -e "${GREEN}[3/3] Deploy completo!${NC}"
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Serviço deployado com sucesso!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}URL:${NC} $SERVICE_URL"
echo ""
echo -e "${YELLOW}Próximos passos:${NC}"
echo "1. Configure Cloud Scheduler para executar diariamente:"
echo "   gcloud scheduler jobs create http ${SERVICE_NAME}-daily \\"
echo "     --schedule='0 0 * * *' \\"
echo "     --uri='${SERVICE_URL}/run' \\"
echo "     --http-method=POST \\"
echo "     --oidc-service-account-email=llmops-runner@${PROJECT_ID}.iam.gserviceaccount.com \\"
echo "     --location=${REGION}"
echo ""
echo "2. Teste manualmente:"
echo "   gcloud run services proxy ${SERVICE_NAME} --region=${REGION}"
echo ""
echo -e "${GREEN}Deploy finalizado!${NC}"

