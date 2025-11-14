"""
Estado do Grafo LangGraph

Define o estado compartilhado entre todos os nós do grafo.
"""

from typing import Annotated, TypedDict


def add_lists(left: list | None, right: list | None) -> list:
    """
    Reducer customizado para acumular listas

    Usado para tools_used e errors que podem ser atualizados
    por múltiplos nós executando em paralelo.
    """
    if left is None:
        left = []
    if right is None:
        return left
    return left + right


class AgentState(TypedDict, total=False):
    """
    Estado do agente durante execução do grafo

    Este estado é passado entre todos os nós e acumula
    informações ao longo da execução.

    Chaves com Annotated[..., add_lists] podem receber múltiplos valores
    de diferentes nós executando em paralelo.
    """

    ticker: str
    analysis_type: str
    period_days: int
    user_id: str | None

    nl2sql_data: dict | None
    nl2sql_context: str
    nl2sql_executed: bool

    websearch_data: dict | None
    websearch_context: str
    websearch_executed: bool

    tools_used: Annotated[list[str], add_lists]
    errors: Annotated[list[str], add_lists]

    analysis_content: str
    validation_result: dict

    cost_usd: float
    total_execution_time_ms: int

    request_id: str

    should_retry: bool
    retry_count: int
