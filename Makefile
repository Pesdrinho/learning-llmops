.PHONY: help setup install dev-install db-up db-down db-init db-reset seed \
        api rag-ingest rag-query eval-rag agents crawler \
        test test-unit test-integration test-e2e \
        lint format pre-commit-install pre-commit-run \
        clean docker-build docker-up docker-down

help: ## Mostra esta mensagem de ajuda
	@echo "LLMOps Lab - Comandos Disponíveis:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ========== Setup e Instalação ==========

setup: ## Configuração inicial completa do projeto
	python -m venv .venv
	@echo "Ative o ambiente virtual com: .venv\Scripts\activate (Windows) ou source .venv/bin/activate (Linux/Mac)"

install: ## Instala dependências base
	pip install -U pip setuptools wheel
	pip install -e .

dev-install: ## Instala dependências de desenvolvimento
	pip install -U pip setuptools wheel
	pip install -e ".[dev]"
	pre-commit install

# ========== Database ==========

db-up: ## Sobe banco de dados local (PostgreSQL + pgvector)
	docker compose -f scripts/local_dev/docker-compose.yml up -d
	@echo "Aguardando PostgreSQL iniciar..."
	@timeout 10 >nul 2>&1 || echo "Banco iniciado"

db-down: ## Para banco de dados local
	docker compose -f scripts/local_dev/docker-compose.yml down

db-init: ## Aplica DDLs no banco (local ou Cloud SQL)
	python scripts/apply_ddls.py

db-reset: db-down db-up db-init ## Reseta banco (cuidado!)

seed: ## Executa seed inicial de dados da Brapi
	python data-schemas/seeds/ingest_sample.py --sample

# ========== Aplicações ==========

api: ## Roda API Blackbox (gateway OpenRouter)
	uvicorn pipelines.api-blackbox.app.main:app --reload --host 0.0.0.0 --port 8000

crawler: ## Executa crawler Brapi manualmente
	python pipelines/crawler-brapi/app/main.py

rag-ingest: ## Executa ingestão de documentos no RAG
	python pipelines/rag/ingest/main.py

rag-query: ## Consulta RAG (use: make rag-query q="sua pergunta")
	python pipelines/rag/retrieval/query.py --q "$(q)"

agents: ## Executa agente NL2SQL (use: make agents q="sua pergunta")
	python pipelines/agents/langgraph/main.py --q "$(q)"

agents-mcp: ## Executa agente com MCP (use: make agents-mcp q="sua pergunta")
	python pipelines/agents-mcp/client_agents/main.py --q "$(q)"

# ========== Avaliações ==========

eval-rag: ## Executa avaliação RAG com Ragas
	python llmops_lab/evals/run_ragas.py

eval-tool-use: ## Executa avaliação de tool use accuracy
	python llmops_lab/evals/tool_use_accuracy.py

# ========== Testes ==========

test: ## Executa todos os testes
	pytest

test-unit: ## Executa apenas testes unitários
	pytest tests/unit -v

test-integration: ## Executa testes de integração
	pytest tests/integration -v

test-e2e: ## Executa testes end-to-end
	pytest tests/e2e -v

# ========== Qualidade de Código ==========

lint: ## Executa linter (ruff)
	ruff check .

format: ## Formata código (ruff + black)
	ruff check --fix .
	ruff format .

pre-commit-install: ## Instala hooks do pre-commit
	pre-commit install

pre-commit-run: ## Executa pre-commit em todos os arquivos
	pre-commit run --all-files

# ========== Docker ==========

docker-build: ## Build de todas as imagens Docker
	docker compose -f scripts/local_dev/docker-compose.yml build

docker-up: ## Sobe todos os serviços Docker
	docker compose -f scripts/local_dev/docker-compose.yml up -d

docker-down: ## Para todos os serviços Docker
	docker compose -f scripts/local_dev/docker-compose.yml down

# ========== Limpeza ==========

clean: ## Remove arquivos temporários e cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true

# ========== Relatórios ==========

cost-report: ## Gera relatório de custos
	python scripts/cost_report.py

# ========== Cloud Deploy ==========

deploy-crawler: ## Deploy crawler para Cloud Run
	bash pipelines/crawler-brapi/deploy.sh

deploy-api: ## Deploy API Blackbox para Cloud Run
	bash pipelines/api-blackbox/deploy.sh

deploy-rag: ## Deploy RAG para Cloud Run
	bash pipelines/rag/deploy.sh

deploy-mcp: ## Deploy MCP Server para Cloud Run
	bash pipelines/agents-mcp/mcp_server/deploy.sh

deploy-all: deploy-crawler deploy-api deploy-rag deploy-mcp ## Deploy de todos os serviços
