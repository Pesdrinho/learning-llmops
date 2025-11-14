"""Modelos Pydantic para API RAG"""

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request para query RAG"""

    query: str = Field(..., description="Pergunta do usuário", min_length=1)
    top_k: int = Field(default=3, description="Número de chunks a recuperar", ge=1, le=10)
    similarity_threshold: float = Field(
        default=0.7, description="Threshold mínimo de similaridade", ge=0.0, le=1.0
    )
    model: str | None = Field(
        default=None, description="Modelo LLM para geração (opcional, usa padrão se não informado)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "Qual foi o último dividendo pago pela Petrobras?",
                "top_k": 3,
                "similarity_threshold": 0.7,
            }
        }


class SourceChunk(BaseModel):
    """Chunk de documento recuperado"""

    source_id: str = Field(..., description="ID do documento fonte")
    content: str = Field(..., description="Conteúdo do chunk")
    similarity: float = Field(..., description="Score de similaridade")
    metadata: dict = Field(default_factory=dict, description="Metadados do chunk")


class QueryResponse(BaseModel):
    """Response da query RAG"""

    answer: str = Field(..., description="Resposta gerada pelo LLM")
    sources: list[SourceChunk] = Field(
        default_factory=list, description="Chunks recuperados usados como contexto"
    )
    metadata: dict = Field(
        default_factory=dict, description="Metadados da geração (modelo, tokens, latência, etc)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "answer": "A Petrobras (PETR4) anunciou dividendos de R$ 0,50 por ação...",
                "sources": [
                    {
                        "source_id": "relatorio_petr4_2024",
                        "content": "Texto do chunk...",
                        "similarity": 0.92,
                        "metadata": {"filename": "relatorio.md"},
                    }
                ],
                "metadata": {
                    "model": "anthropic/claude-3.5-sonnet",
                    "input_tokens": 1500,
                    "output_tokens": 250,
                    "latency_ms": 1850,
                },
            }
        }


class HealthResponse(BaseModel):
    """Response do health check"""

    status: str = Field(..., description="Status da API")
    version: str = Field(default="1.0.0", description="Versão da API")
    database: str = Field(..., description="Status da conexão com banco")
