"""
Modelos Pydantic para o Pipeline de Agentes

Define schemas para requisições e respostas da API.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AnalysisRequest(BaseModel):
    """
    Requisição de análise de ação

    Exemplo:
        {
            "ticker": "PETR4",
            "analysis_type": "price_movement",
            "period_days": 90
        }
    """

    ticker: str = Field(
        ...,
        description="Código da ação (ex: PETR4, VALE3)",
        min_length=4,
        max_length=10,
        json_schema_extra={"example": "PETR4"},
    )

    analysis_type: str = Field(
        ...,
        description="Tipo de análise a ser realizada",
        json_schema_extra={
            "example": "price_movement",
            "enum": [
                "price_movement",
                "volume_analysis",
                "trend_analysis",
                "support_resistance",
                "comparative_analysis",
            ],
        },
    )

    period_days: int = Field(
        default=90,
        description="Período em dias para análise",
        ge=7,
        le=730,
        json_schema_extra={"example": 90},
    )

    user_id: str | None = Field(
        default=None,
        description="ID do usuário (opcional)",
        json_schema_extra={"example": "user123"},
    )

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        """Valida e normaliza ticker"""
        ticker = v.strip().upper()
        if not ticker.replace(".", "").isalnum():
            raise ValueError("Ticker deve conter apenas letras, números e ponto")
        return ticker

    @field_validator("analysis_type")
    @classmethod
    def validate_analysis_type(cls, v: str) -> str:
        """Valida tipo de análise"""
        valid_types = [
            "price_movement",
            "volume_analysis",
            "trend_analysis",
            "support_resistance",
            "comparative_analysis",
        ]
        if v not in valid_types:
            raise ValueError(
                f"analysis_type deve ser um de: {', '.join(valid_types)}. Recebido: {v}"
            )
        return v


class AnalysisResponse(BaseModel):
    """
    Resposta de análise de ação

    Exemplo:
        {
            "ticker": "PETR4",
            "analysis_type": "price_movement",
            "content": "# Análise de Movimentação...",
            "tools_used": ["nl2sql", "websearch"],
            "cost_usd": 0.05,
            "latency_ms": 3500,
            "request_id": "abc-123",
            "export_paths": {
                "file_path": "/exports/PETR4_price_movement_20240101.md",
                "db_id": 123
            },
            "created_at": "2024-01-01T12:00:00Z"
        }
    """

    ticker: str = Field(..., description="Código da ação analisada")

    analysis_type: str = Field(..., description="Tipo de análise realizada")

    content: str = Field(..., description="Conteúdo da análise em markdown")

    tools_used: list[str] = Field(..., description="Ferramentas utilizadas na análise")

    cost_usd: float = Field(..., description="Custo da análise em USD", ge=0)

    latency_ms: int = Field(..., description="Latência da análise em ms", ge=0)

    request_id: str = Field(..., description="ID único da requisição")

    export_paths: dict[str, Any] = Field(
        ...,
        description="Caminhos de exportação (file_path, db_id)",
        json_schema_extra={"example": {"file_path": "/exports/PETR4.md", "db_id": 123}},
    )

    created_at: datetime = Field(
        default_factory=datetime.now, description="Timestamp da criação da análise"
    )


class ChatMessage(BaseModel):
    """Mensagem de chat (compatibilidade com OpenRouter)"""

    role: str = Field(..., description="Papel da mensagem (user, assistant, system)")
    content: str = Field(..., description="Conteúdo da mensagem")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Valida role"""
        if v not in ["user", "assistant", "system"]:
            raise ValueError("role deve ser 'user', 'assistant' ou 'system'")
        return v


class Usage(BaseModel):
    """Uso de tokens"""

    prompt_tokens: int = Field(..., description="Tokens usados no prompt", ge=0)
    completion_tokens: int = Field(..., description="Tokens usados na completion", ge=0)
    total_tokens: int = Field(..., description="Total de tokens", ge=0)


class HealthResponse(BaseModel):
    """Resposta do health check"""

    status: str = Field(..., description="Status geral (healthy, degraded, unhealthy)")
    version: str = Field(..., description="Versão da API")
    timestamp: datetime = Field(..., description="Timestamp do check")
    checks: dict[str, Any] = Field(..., description="Status de cada componente")


class ErrorDetail(BaseModel):
    """Detalhe de erro"""

    error: str = Field(..., description="Tipo/código do erro")
    message: str = Field(..., description="Mensagem descritiva do erro")
    request_id: str = Field(..., description="ID da requisição que causou o erro")
    details: dict[str, Any] | None = Field(default=None, description="Detalhes adicionais do erro")


class ToolExecutionResult(BaseModel):
    """Resultado da execução de uma ferramenta"""

    tool_name: str = Field(..., description="Nome da ferramenta executada")
    success: bool = Field(..., description="Se a execução foi bem-sucedida")
    data: dict[str, Any] | None = Field(default=None, description="Dados retornados")
    error: str | None = Field(default=None, description="Mensagem de erro (se falhou)")
    execution_time_ms: int = Field(..., description="Tempo de execução em ms", ge=0)


class AnalysisMetadata(BaseModel):
    """Metadados de uma análise"""

    ticker: str
    analysis_type: str
    period_days: int
    tools_used: list[str]
    cost_usd: float
    latency_ms: int
    request_id: str
    nl2sql_executed: bool = False
    websearch_executed: bool = False
    data_points: int | None = None
    validation_passed: bool = True
