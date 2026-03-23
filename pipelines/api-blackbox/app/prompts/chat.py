"""
Prompts para Chat Completion

Templates otimizados para conversação geral com guardrails
de segurança e compliance.
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from prompts.base import PromptConfig, registry

CHAT_SYSTEM_PROMPT = """Você é um assistente financeiro especializado em mercado brasileiro.

Seu papel é ajudar usuários com informações sobre:
- Ações da B3 (Bolsa de Valores Brasileira)
- Fundos de investimento
- Renda fixa e variável
- Análise de mercado
- Educação financeira básica

## Diretrizes

- Seja claro, objetivo e educativo
- Use linguagem acessível, evitando jargões desnecessários
- Sempre mencione que não está dando recomendação de investimento
- Não forneça previsões definitivas sobre o mercado
- Cite fontes quando possível

## Restrições

- NÃO forneça recomendações específicas de compra/venda
- NÃO faça promessas de retorno ou ganhos garantidos
- NÃO processe informações pessoais sensíveis (CPF, senhas, etc)
- NÃO responda sobre tópicos fora do escopo financeiro
"""


CHAT_CONVERSATION_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system", CHAT_SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="messages"),
    ]
)


CHAT_SINGLE_TURN_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system", CHAT_SYSTEM_PROMPT),
        ("user", "{query}"),
    ]
)


FINANCIAL_ADVISOR_SYSTEM_PROMPT = """Você é um assistente especializado em análise financeira do mercado brasileiro.

Seu objetivo é fornecer análises educativas sobre:
- Indicadores fundamentalistas de ações
- Tendências de mercado
- Análise técnica básica
- Diversificação de portfólio

Sempre enfatize:
1. A importância da diversificação
2. O risco inerente a investimentos
3. A necessidade de análise própria ou consultoria profissional

IMPORTANTE: Suas respostas são meramente educativas e não constituem recomendação de investimento."""


FINANCIAL_ADVISOR_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system", FINANCIAL_ADVISOR_SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="messages"),
    ]
)


chat_config = PromptConfig(
    version="1.0.0",
    description="Prompt para chat completion geral com guardrails financeiros",
    variables=["messages"],
    guardrails={
        "enable_topic_validation": True,
        "allowed_topics": [
            "ações",
            "bolsa de valores",
            "investimentos",
            "renda fixa",
            "fundos",
            "economia",
            "mercado financeiro",
        ],
        "enable_injection_detection": True,
        "enable_pii_masking": True,
    },
)

financial_advisor_config = PromptConfig(
    version="1.0.0",
    description="Prompt especializado para análise financeira educativa",
    variables=["messages"],
    guardrails={
        "enable_topic_validation": True,
        "allowed_topics": [
            "análise fundamentalista",
            "análise técnica",
            "indicadores financeiros",
            "balanço patrimonial",
            "demonstrações financeiras",
        ],
        "enable_injection_detection": True,
        "enable_output_validation": True,
    },
)

single_turn_config = PromptConfig(
    version="1.0.0",
    description="Prompt para perguntas simples sem histórico de conversa",
    variables=["query"],
    guardrails={
        "enable_topic_validation": True,
        "enable_injection_detection": True,
    },
)


registry.register("chat_conversation", CHAT_CONVERSATION_TEMPLATE, chat_config)
registry.register("financial_advisor", FINANCIAL_ADVISOR_TEMPLATE, financial_advisor_config)
registry.register("chat_single_turn", CHAT_SINGLE_TURN_TEMPLATE, single_turn_config)


def get_chat_prompt(
    conversation_type: str = "chat_conversation", version: str | None = None
) -> tuple[ChatPromptTemplate, PromptConfig]:
    """
    Obtém template de chat registrado

    Args:
        conversation_type: Tipo de conversa (chat_conversation, financial_advisor, chat_single_turn)
        version: Versão específica (None = mais recente)

    Returns:
        Tupla (template, config)
    """
    return registry.get(conversation_type, version)


def get_system_prompt(conversation_type: str = "chat_conversation") -> str:
    """
    Obtém apenas o system prompt de um tipo de conversa

    Args:
        conversation_type: Tipo de conversa

    Returns:
        System prompt como string
    """
    prompts_map = {
        "chat_conversation": CHAT_SYSTEM_PROMPT,
        "financial_advisor": FINANCIAL_ADVISOR_SYSTEM_PROMPT,
    }

    return prompts_map.get(conversation_type, CHAT_SYSTEM_PROMPT)
