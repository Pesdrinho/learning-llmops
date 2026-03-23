"""
Schemas Pydantic para API Blackbox

Este arquivo define os contratos de dados (schemas) para a API.
Usamos Pydantic para validação automática, serialização e documentação.

Por que Pydantic?
- Validação automática de tipos
- Mensagens de erro claras
- Geração automática de documentação OpenAPI
- Conversão de tipos (coercion)
- Performance (escrito em Rust desde v2)
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ==================== MENSAGENS DE CHAT ====================


class ChatMessage(BaseModel):
    """
    Representa uma mensagem no formato ChatML

    ChatML é o formato padrão para conversação com LLMs:
    - system: Instruções para o modelo (comportamento)
    - user: Mensagens do usuário
    - assistant: Respostas do assistente
    - function/tool: Respostas de ferramentas (opcional)

    Exemplo:
        {
            "role": "user",
            "content": "Qual a cotação da PETR4?"
        }
    """

    role: Literal["system", "user", "assistant", "function", "tool"] = Field(
        ..., description="Papel da mensagem no diálogo"
    )

    content: str = Field(
        ...,
        description="Conteúdo textual da mensagem",
        min_length=1,
        max_length=50000,  # Proteção contra mensagens muito longas
    )

    name: str | None = Field(
        None, description="Nome do participante (opcional, usado em multi-agentes)"
    )

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        """Valida que o conteúdo não é apenas espaços"""
        if not v.strip():
            raise ValueError("Conteúdo não pode ser vazio")
        return v


# ==================== REQUESTS ====================


class ChatRequest(BaseModel):
    """
    Requisição para o endpoint /chat

    Este é o contrato principal da API. Define como o cliente
    deve enviar requisições de chat.

    Campos importantes:
    - messages: Histórico da conversa
    - model: Qual LLM usar (roteado via OpenRouter)
    - temperature: Criatividade (0=determinístico, 1=criativo)
    - max_tokens: Limite de tokens na resposta

    Exemplo de uso:
        POST /chat
        {
            "messages": [
                {"role": "user", "content": "Olá!"}
            ],
            "model": "openai/gpt-4o-mini",
            "temperature": 0.7
        }
    """

    messages: list[ChatMessage] = Field(
        ...,
        description="Lista de mensagens no formato ChatML",
        min_length=1,
        max_length=100,  # Proteção contra loops infinitos
    )

    model: str = Field(
        "openai/gpt-4o-mini",
        description="Identificador do modelo LLM (ex: openai/gpt-4o-mini, anthropic/claude-3.5-sonnet)",
        examples=[
            "openai/gpt-4o-mini",
            "anthropic/claude-3.5-sonnet",
            "meta-llama/llama-3.1-8b-instruct",
        ],
    )

    temperature: float = Field(
        0.7,
        description="Temperatura de amostragem (0.0 a 2.0). Maior = mais criativo",
        ge=0.0,
        le=2.0,
    )

    max_tokens: int | None = Field(
        None,
        description="Máximo de tokens na resposta. None = sem limite",
        gt=0,
        le=4096,  # Proteção de custos
    )

    top_p: float = Field(
        1.0, description="Nucleus sampling (0.0 a 1.0). Alternativa à temperature", ge=0.0, le=1.0
    )

    stream: bool = Field(
        False, description="Se True, retorna resposta em streaming (Server-Sent Events)"
    )

    user_id: str | None = Field(None, description="ID do usuário (para tracking e rate limiting)")


class ChatCompletionRequest(ChatRequest):
    """
    Requisição para o endpoint /chat/completion com guardrails

    Herda de ChatRequest e adiciona configurações de segurança
    e validação através de guardrails.
    """

    enable_guardrails: bool = Field(True, description="Se True, aplica guardrails de validação")

    allowed_topics: list[str] | None = Field(
        None, description="Lista de tópicos permitidos (None = usa padrão financeiro)"
    )

    conversation_type: str = Field(
        "chat_conversation",
        description="Tipo de conversa (chat_conversation, financial_advisor)",
        examples=["chat_conversation", "financial_advisor"],
    )

    enable_cache: bool = Field(
        False, description="Se True, usa cache de respostas para queries repetidas"
    )


class DatasetGenerationRequest(BaseModel):
    """
    Requisição para geração de dataset de fine-tuning

    Gera exemplos formatados no padrão Qwen para tool calling.
    """

    tool_name: str = Field(..., description="Nome da tool/função", min_length=1, max_length=100)

    tool_description: str = Field(
        ..., description="Descrição detalhada do que a tool faz", min_length=10, max_length=1000
    )

    tool_schema: dict = Field(
        ..., description="Schema JSON da tool (OpenAPI-like com name, description, parameters)"
    )

    num_examples: int = Field(10, description="Número de exemplos a gerar", ge=1, le=100)

    diversity_level: float = Field(
        0.7,
        description="Nível de diversidade dos exemplos (0.0 = similar, 1.0 = muito diverso)",
        ge=0.0,
        le=1.0,
    )

    output_format: Literal["jsonl", "array"] = Field(
        "jsonl", description="Formato de saída: 'jsonl' (linha por linha) ou 'array' (JSON array)"
    )

    model: str = Field(
        "anthropic/claude-3.5-sonnet",
        description="Modelo a usar para gerar exemplos (recomendado: Claude ou GPT-4)",
    )

    user_id: str | None = Field(None, description="ID do usuário (para tracking)")


# ==================== RESPONSES ====================


class UsageInfo(BaseModel):
    """
    Informações de uso de tokens

    Tokens são unidades de texto processadas pelo LLM.
    Aproximadamente: 1 token ≈ 0.75 palavras em português

    Importante para:
    - Cálculo de custos (cobrado por token)
    - Métricas de eficiência
    - Detecção de anomalias
    """

    prompt_tokens: int = Field(..., description="Número de tokens na entrada (mensagens enviadas)")

    completion_tokens: int = Field(..., description="Número de tokens na saída (resposta gerada)")

    total_tokens: int = Field(..., description="Total de tokens processados (prompt + completion)")


class ChatResponse(BaseModel):
    """
    Resposta do endpoint /chat

    Estrutura inspirada na OpenAI API para compatibilidade.

    Campos importantes:
    - message: Resposta do assistente
    - usage: Estatísticas de uso
    - cost_usd: Custo da requisição
    - latency_ms: Tempo de resposta
    """

    message: ChatMessage = Field(..., description="Resposta gerada pelo modelo")

    model: str = Field(..., description="Modelo que gerou a resposta")

    usage: UsageInfo = Field(..., description="Informações de consumo de tokens")

    cost_usd: float = Field(..., description="Custo desta requisição em dólares", ge=0.0)

    latency_ms: int = Field(..., description="Latência da requisição em milissegundos", ge=0)

    created_at: datetime = Field(default_factory=datetime.now, description="Timestamp da resposta")

    request_id: str = Field(..., description="ID único da requisição (para debugging)")


# ==================== MODELOS DISPONÍVEIS ====================


class ModelInfo(BaseModel):
    """
    Informações sobre um modelo disponível

    Metadados importantes para o cliente escolher
    qual modelo usar com base em suas necessidades.
    """

    id: str = Field(
        ...,
        description="Identificador único do modelo",
        examples=["openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet", "deepseek/deepseek-chat"],
    )

    name: str = Field(..., description="Nome amigável do modelo")

    provider: str = Field(..., description="Provider do modelo (ex: OpenAI, Anthropic)")

    input_cost_per_1k: float = Field(
        ..., description="Custo por 1k tokens de entrada (USD)", ge=0.0
    )

    output_cost_per_1k: float = Field(..., description="Custo por 1k tokens de saída (USD)", ge=0.0)

    context_window: int = Field(..., description="Tamanho máximo do contexto (tokens)", gt=0)

    description: str = Field(..., description="Descrição das características do modelo")


class ModelsResponse(BaseModel):
    """
    Resposta do endpoint /models

    Lista todos os modelos disponíveis com suas características.
    """

    models: list[ModelInfo] = Field(..., description="Lista de modelos disponíveis")

    total: int = Field(..., description="Total de modelos disponíveis")


# ==================== HEALTH CHECK ====================


class HealthResponse(BaseModel):
    """
    Resposta do endpoint /health

    Health check para monitoramento e load balancers.
    """

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ..., description="Status geral do serviço"
    )

    version: str = Field(..., description="Versão da API")

    timestamp: datetime = Field(
        default_factory=datetime.now, description="Timestamp do health check"
    )

    checks: dict = Field(..., description="Status de dependências (database, openrouter, etc)")


# ==================== ERROS ====================


class DatasetGenerationResponse(BaseModel):
    """
    Resposta do endpoint de geração de dataset

    Retorna exemplos formatados para fine-tuning.
    """

    examples: list[dict] = Field(..., description="Lista de exemplos gerados no formato Qwen")

    count: int = Field(..., description="Número de exemplos gerados")

    format: str = Field(..., description="Formato dos exemplos (jsonl ou array)")

    tool_name: str = Field(..., description="Nome da tool para qual foram gerados exemplos")

    cost_usd: float = Field(..., description="Custo da geração em dólares", ge=0.0)

    model_used: str = Field(..., description="Modelo LLM utilizado para gerar exemplos")

    latency_ms: int = Field(..., description="Latência total da geração em milissegundos", ge=0)

    created_at: datetime = Field(default_factory=datetime.now, description="Timestamp da geração")

    request_id: str = Field(..., description="ID único da requisição")


class ErrorDetail(BaseModel):
    """
    Detalhes de um erro

    Formato padronizado para erros, facilitando tratamento no cliente.
    """

    error: str = Field(..., description="Tipo do erro")

    message: str = Field(..., description="Mensagem descritiva do erro")

    details: dict | None = Field(None, description="Informações adicionais sobre o erro")

    request_id: str | None = Field(None, description="ID da requisição que causou o erro")
