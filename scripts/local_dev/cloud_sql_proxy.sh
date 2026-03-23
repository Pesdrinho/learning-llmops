#!/bin/bash

# Script para iniciar Cloud SQL Proxy
# Permite conexão local com Cloud SQL

set -e

# Carrega variáveis do .env se existir
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Verifica se DB_CONNECTION_NAME está configurado
if [ -z "$DB_CONNECTION_NAME" ]; then
    echo "Erro: DB_CONNECTION_NAME não configurado"
    echo "Configure no arquivo .env: DB_CONNECTION_NAME=project:region:instance"
    exit 1
fi

# Verifica se cloud-sql-proxy está instalado
if ! command -v cloud-sql-proxy &> /dev/null; then
    echo "Cloud SQL Proxy não encontrado. Instalando..."
    
    # Detecta sistema operacional
    OS=$(uname -s)
    ARCH=$(uname -m)
    
    if [ "$OS" = "Linux" ]; then
        if [ "$ARCH" = "x86_64" ]; then
            curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.0/cloud-sql-proxy.linux.amd64
        else
            curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.0/cloud-sql-proxy.linux.arm64
        fi
    elif [ "$OS" = "Darwin" ]; then
        if [ "$ARCH" = "x86_64" ]; then
            curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.0/cloud-sql-proxy.darwin.amd64
        else
            curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.0/cloud-sql-proxy.darwin.arm64
        fi
    else
        echo "Sistema operacional não suportado: $OS"
        exit 1
    fi
    
    chmod +x cloud-sql-proxy
    sudo mv cloud-sql-proxy /usr/local/bin/
    echo "Cloud SQL Proxy instalado com sucesso!"
fi

# Porta local (padrão 5432)
LOCAL_PORT=${DB_PORT:-5432}

echo "Iniciando Cloud SQL Proxy..."
echo "Conexão: $DB_CONNECTION_NAME"
echo "Porta local: $LOCAL_PORT"
echo ""
echo "Para conectar, use:"
echo "  Host: localhost"
echo "  Port: $LOCAL_PORT"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"
echo ""
echo "Pressione Ctrl+C para parar"
echo ""

# Inicia proxy
cloud-sql-proxy \
    --port=$LOCAL_PORT \
    $DB_CONNECTION_NAME




