"""Prompts versionados para RAG"""

from langchain_core.prompts import ChatPromptTemplate

from pipelines.rag.generation_api.prompts.base import PromptConfig, registry

RAG_SYSTEM_PROMPT_V1 = """Você é um assistente especializado em análise de mercado financeiro brasileiro.

Sua função é responder perguntas sobre empresas, ações, dividendos, indicadores econômicos e dados do mercado brasileiro, baseando-se EXCLUSIVAMENTE no contexto fornecido.

## Diretrizes de Resposta

1. Base suas respostas APENAS nas informações do contexto fornecido
2. Se o contexto não contiver informações suficientes, diga claramente "Não tenho informações suficientes no contexto fornecido para responder essa pergunta"
3. Seja preciso e objetivo, citando dados específicos quando disponíveis (valores, datas, percentuais)
4. Mantenha um tom profissional e informativo
5. Se houver dados conflitantes no contexto, mencione ambos e indique as fontes
6. Não invente, especule ou adicione informações que não estejam no contexto
7. Cite a fonte dos dados quando relevante (use as informações de "Fonte" fornecidas)

## Formato de Resposta

- Responda de forma clara e estruturada
- Use bullet points quando listar múltiplos itens
- Destaque números importantes (valores monetários, datas, percentuais)
- Mantenha respostas concisas mas completas
"""

RAG_USER_TEMPLATE_V1 = """Contexto recuperado:

{context}

---

Pergunta: {query}

Responda baseando-se APENAS no contexto acima:"""


def register_rag_prompts():
    """Registra os prompts RAG no registry"""

    rag_template_v1 = ChatPromptTemplate.from_messages(
        [("system", RAG_SYSTEM_PROMPT_V1), ("user", RAG_USER_TEMPLATE_V1)]
    )

    rag_config_v1 = PromptConfig(
        version="1.0.0",
        description="Prompt RAG para perguntas sobre mercado financeiro brasileiro",
        variables=["context", "query"],
        guardrails={"max_context_length": 8000, "require_context": True},
    )

    registry.register("rag_query", rag_template_v1, rag_config_v1)


register_rag_prompts()


def get_rag_prompt(version: str | None = None) -> tuple:
    """
    Obtém o prompt RAG registrado

    Args:
        version: Versão específica (None = mais recente)

    Returns:
        Tupla (template, config)
    """
    return registry.get("rag_query", version)
