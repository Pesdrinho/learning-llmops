"""
Construtor do Grafo LangGraph

Define a estrutura e fluxo de execução do grafo de agentes.
"""

from graph.nodes import (
    end_node,
    nl2sql_node,
    router_node,
    synthesis_node,
    validation_node,
    websearch_node,
)
from graph.state import AgentState
from langgraph.graph import END, StateGraph

from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


def should_retry(state: AgentState) -> str:
    """
    Decide se deve tentar novamente ou finalizar

    Args:
        state: Estado atual

    Returns:
        Nome do próximo nó
    """
    if state.get("should_retry", False):
        logger.info("[Router] Retrying synthesis")
        return "synthesis"
    return "end"


def build_agent_graph() -> StateGraph:
    """
    Constrói o grafo de agentes

    Fluxo:
        START → router
        router → [nl2sql, websearch] (paralelo)
        [nl2sql, websearch] → synthesis (espera ambos)
        synthesis → validation
        validation → end (ou retry → synthesis)

    Nota: nl2sql e websearch executam em paralelo.
    Para evitar conflitos, cada nó retorna apenas as chaves que modifica.
    O estado usa Annotated[list, add] para acumular valores de múltiplos nós.

    Returns:
        Grafo compilado
    """
    logger.info("🏗️  Construindo grafo de agentes")

    workflow = StateGraph(AgentState)

    workflow.add_node("router", router_node)
    workflow.add_node("nl2sql", nl2sql_node)
    workflow.add_node("websearch", websearch_node)
    workflow.add_node("synthesis", synthesis_node)
    workflow.add_node("validation", validation_node)
    workflow.add_node("end", end_node)

    workflow.set_entry_point("router")

    workflow.add_edge("router", "nl2sql")
    workflow.add_edge("router", "websearch")

    workflow.add_edge("nl2sql", "synthesis")
    workflow.add_edge("websearch", "synthesis")

    workflow.add_edge("synthesis", "validation")

    workflow.add_conditional_edges(
        "validation",
        should_retry,
        {
            "synthesis": "synthesis",
            "end": "end",
        },
    )

    workflow.add_edge("end", END)

    graph = workflow.compile()

    logger.info("✅ Grafo de agentes construído com sucesso")

    return graph


_graph_instance = None


def get_agent_graph() -> StateGraph:
    """
    Retorna instância singleton do grafo

    Returns:
        Grafo compilado
    """
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_agent_graph()
    return _graph_instance
