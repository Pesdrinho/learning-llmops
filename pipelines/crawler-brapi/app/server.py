"""
Servidor FastAPI para Cloud Run - Crawler Brapi
Expõe endpoints HTTP para executar o crawler via triggers
"""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from main_crawler import run_full_crawl

from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle do app"""
    logger.info("Servidor iniciado e pronto para receber requisições")
    yield
    logger.info("Servidor encerrado")


# Cria app FastAPI
app = FastAPI(
    title="Crawler Brapi API",
    description="API para executar crawler de dados financeiros",
    version="1.0.1",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "crawler-brapi",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """Health check detalhado"""
    return {
        "status": "healthy",
        "service": "crawler-brapi",
        "environment": os.getenv("APP_ENV", "unknown"),
    }


@app.post("/run")
async def run_crawler(sample: bool = False):
    """
    Executa o crawler completo

    Query params:
        sample: Se True, executa apenas amostra (para testes)

    Returns:
        JSON com status da execução
    """
    logger.info(f"Recebida requisição para executar crawler (sample={sample})")

    try:
        await run_full_crawl(sample=sample)

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Crawler executado com sucesso",
                "mode": "sample" if sample else "full"
            }
        )

    except Exception as e:
        logger.error(f"Erro ao executar crawler: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao executar crawler: {str(e)}"
        )


@app.post("/run/sample")
async def run_crawler_sample():
    """Atalho para executar crawler em modo sample"""
    return await run_crawler(sample=True)


@app.post("/run/full")
async def run_crawler_full():
    """Atalho para executar crawler em modo full"""
    return await run_crawler(sample=False)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )

