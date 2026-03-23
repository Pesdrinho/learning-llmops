"""
API de Geração RAG - FastAPI Application

Expõe endpoints para queries RAG com busca vetorial e geração de respostas
"""

import time

import psycopg2
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from llmops_lab.logging.logger import get_logger
from pipelines.rag.generation_api.config import DATABASE_URL
from pipelines.rag.generation_api.generator import RAGGenerator
from pipelines.rag.generation_api.models import (
    HealthResponse,
    QueryRequest,
    QueryResponse,
)
from pipelines.rag.generation_api.retriever import RAGRetriever

logger = get_logger(__name__)

app = FastAPI(
    title="RAG Generation API",
    description="API para queries com Retrieval Augmented Generation",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

retriever = RAGRetriever()
generator = RAGGenerator()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware para logging de requests"""
    start_time = time.time()

    logger.info(f"Request: {request.method} {request.url.path}")

    response = await call_next(request)

    duration_ms = int((time.time() - start_time) * 1000)
    logger.info(f"Response: {response.status_code} | Duration: {duration_ms}ms")

    return response


@app.get("/", tags=["root"])
async def root():
    """Root endpoint"""
    return {
        "service": "RAG Generation API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {"health": "/health", "query": "POST /query"},
    }


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """Health check endpoint"""

    db_status = "healthy"
    try:
        conn = psycopg2.connect(DATABASE_URL)
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.close()
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
        logger.error(f"Database health check failed: {e}")

    status = "healthy" if db_status == "healthy" else "degraded"

    return HealthResponse(status=status, version="1.0.0", database=db_status)


@app.post("/query", response_model=QueryResponse, tags=["rag"])
async def query_rag(request: QueryRequest):
    """
    Endpoint principal para queries RAG

    Fluxo:
    1. Gera embedding da query
    2. Busca chunks similares no banco (similaridade cosseno)
    3. Compõe prompt com contexto recuperado
    4. Gera resposta usando LLM via OpenRouter
    5. Retorna resposta + fontes + metadata
    """
    try:
        logger.info(
            f"Query recebida: '{request.query[:100]}...' | "
            f"top_k: {request.top_k}, "
            f"threshold: {request.similarity_threshold}, "
            f"model: {request.model}"
        )

        chunks = retriever.retrieve(
            query=request.query,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
        )

        if not chunks:
            logger.warning("Nenhum chunk recuperado com threshold especificado")
            return QueryResponse(
                answer="Não encontrei informações relevantes para responder sua pergunta. "
                "Tente reformular ou fazer uma pergunta mais específica.",
                sources=[],
                metadata={"chunks_retrieved": 0, "message": "no_relevant_context"},
            )

        logger.info(
            f"Chunks recuperados: {len(chunks)} | "
            f"Similaridades: [{', '.join(f'{c.similarity:.3f}' for c in chunks[:3])}...]"
        )

        for i, chunk in enumerate(chunks, 1):
            logger.debug(
                f"Chunk {i}: source_id={chunk.source_id}, "
                f"similarity={chunk.similarity:.3f}, "
                f"tamanho={len(chunk.content)} caracteres"
            )

        answer, metadata = generator.generate(
            query=request.query, chunks=chunks, model=request.model
        )

        return QueryResponse(answer=answer, sources=chunks, metadata=metadata)

    except Exception as e:
        logger.error(f"Erro ao processar query: {e}", exc_info=True)
        raise Exception(f"Erro ao processar query: {str(e)}") from e


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handler global de exceções"""
    logger.error(f"Exceção não tratada: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "internal_server_error", "message": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8888)
