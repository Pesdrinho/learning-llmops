"""
Prompts para Análise de Ações

Templates LangChain para diferentes tipos de análise financeira.
"""

from langchain_core.prompts import ChatPromptTemplate
from prompts.base import PromptConfig, registry

ANALYSIS_SYSTEM_PROMPT = """Você é um analista financeiro especializado em ações da B3 (Bolsa de Valores Brasileira).

Seu papel é analisar dados históricos e informações de mercado para gerar análises técnicas educativas sobre ações.

## Diretrizes

- Seja objetivo e baseie-se nos dados fornecidos
- Use linguagem técnica mas acessível
- Apresente os dados de forma clara com tabelas e gráficos descritivos
- Identifique padrões, tendências e pontos de atenção
- Sempre mencione que a análise é educativa e não constitui recomendação de investimento

## Restrições

- NÃO forneça recomendações de compra ou venda
- NÃO faça promessas de retorno futuro
- NÃO invente dados que não foram fornecidos
- SEMPRE cite as fontes dos dados (SQL, Web, etc)

## Formato de Resposta

Suas análises devem estar em formato Markdown com:
- Título principal (# Análise de {ticker})
- Seções organizadas (## Resumo, ## Dados Históricos, ## Análise, ## Conclusão)
- Uso de tabelas, listas e destaques quando apropriado
- Citação de fontes ao final
"""

PRICE_MOVEMENT_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system", ANALYSIS_SYSTEM_PROMPT),
        (
            "user",
            """Analise a movimentação de preço da ação {ticker} com base nos dados abaixo.

## Dados OHLCV (SQL)
{nl2sql_context}

## Informações da Web
{websearch_context}

Por favor, gere uma análise completa da movimentação de preço nos últimos {period_days} dias, incluindo:
1. Resumo da variação no período
2. Identificação de tendências (alta, baixa, lateral)
3. Volatilidade e amplitude de preços
4. Pontos de destaque (máximas, mínimas)
5. Contexto de mercado (se disponível)
6. Conclusão educativa

Formato: Markdown estruturado.""",
        ),
    ]
)

VOLUME_ANALYSIS_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system", ANALYSIS_SYSTEM_PROMPT),
        (
            "user",
            """Analise o volume de negociação da ação {ticker} com base nos dados abaixo.

## Dados OHLCV (SQL)
{nl2sql_context}

## Informações da Web
{websearch_context}

Por favor, gere uma análise completa do volume de negociação nos últimos {period_days} dias, incluindo:
1. Volume médio e total do período
2. Dias de maior e menor volume
3. Relação entre volume e movimento de preço
4. Liquidez da ação
5. Padrões de volume observados
6. Conclusão sobre a liquidez e interesse do mercado

Formato: Markdown estruturado.""",
        ),
    ]
)

TREND_ANALYSIS_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system", ANALYSIS_SYSTEM_PROMPT),
        (
            "user",
            """Identifique e analise tendências da ação {ticker} com base nos dados abaixo.

## Dados OHLCV (SQL)
{nl2sql_context}

## Informações da Web
{websearch_context}

Por favor, gere uma análise completa de tendências nos últimos {period_days} dias, incluindo:
1. Identificação da tendência principal (alta, baixa, lateral)
2. Força da tendência
3. Mudanças de tendência no período
4. Médias móveis e direção
5. Contexto de mercado e setor
6. Perspectivas técnicas (educativas)

Formato: Markdown estruturado.""",
        ),
    ]
)

SUPPORT_RESISTANCE_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system", ANALYSIS_SYSTEM_PROMPT),
        (
            "user",
            """Identifique suportes e resistências da ação {ticker} com base nos dados abaixo.

## Dados OHLCV (SQL)
{nl2sql_context}

## Informações da Web
{websearch_context}

Por favor, gere uma análise técnica de suportes e resistências nos últimos {period_days} dias, incluindo:
1. Principais níveis de suporte identificados
2. Principais níveis de resistência identificados
3. Histórico de testes desses níveis
4. Rompimentos e pullbacks
5. Canais de preço
6. Implicações técnicas (educativas)

Formato: Markdown estruturado.""",
        ),
    ]
)

COMPARATIVE_ANALYSIS_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system", ANALYSIS_SYSTEM_PROMPT),
        (
            "user",
            """Compare o desempenho da ação {ticker} com o mercado com base nos dados abaixo.

## Dados OHLCV (SQL)
{nl2sql_context}

## Informações da Web
{websearch_context}

Por favor, gere uma análise comparativa nos últimos {period_days} dias, incluindo:
1. Performance da ação no período
2. Comparação com índice Ibovespa (se disponível)
3. Comparação com setor (se disponível)
4. Fatores que explicam a performance relativa
5. Posicionamento da ação no mercado
6. Conclusão sobre performance relativa

Formato: Markdown estruturado.""",
        ),
    ]
)


price_movement_config = PromptConfig(
    version="1.0.0",
    description="Análise de movimentação de preço de ações",
    variables=["ticker", "period_days", "nl2sql_context", "websearch_context"],
    guardrails={
        "enable_output_validation": True,
        "min_length": 500,
        "require_markdown": True,
    },
)

volume_analysis_config = PromptConfig(
    version="1.0.0",
    description="Análise de volume de negociação",
    variables=["ticker", "period_days", "nl2sql_context", "websearch_context"],
    guardrails={
        "enable_output_validation": True,
        "min_length": 500,
        "require_markdown": True,
    },
)

trend_analysis_config = PromptConfig(
    version="1.0.0",
    description="Análise de tendências da ação",
    variables=["ticker", "period_days", "nl2sql_context", "websearch_context"],
    guardrails={
        "enable_output_validation": True,
        "min_length": 500,
        "require_markdown": True,
    },
)

support_resistance_config = PromptConfig(
    version="1.0.0",
    description="Análise de suportes e resistências",
    variables=["ticker", "period_days", "nl2sql_context", "websearch_context"],
    guardrails={
        "enable_output_validation": True,
        "min_length": 500,
        "require_markdown": True,
    },
)

comparative_analysis_config = PromptConfig(
    version="1.0.0",
    description="Análise comparativa de desempenho",
    variables=["ticker", "period_days", "nl2sql_context", "websearch_context"],
    guardrails={
        "enable_output_validation": True,
        "min_length": 500,
        "require_markdown": True,
    },
)


registry.register("price_movement", PRICE_MOVEMENT_TEMPLATE, price_movement_config)
registry.register("volume_analysis", VOLUME_ANALYSIS_TEMPLATE, volume_analysis_config)
registry.register("trend_analysis", TREND_ANALYSIS_TEMPLATE, trend_analysis_config)
registry.register("support_resistance", SUPPORT_RESISTANCE_TEMPLATE, support_resistance_config)
registry.register(
    "comparative_analysis", COMPARATIVE_ANALYSIS_TEMPLATE, comparative_analysis_config
)


def get_analysis_prompt(
    analysis_type: str, version: str | None = None
) -> tuple[ChatPromptTemplate, PromptConfig]:
    """
    Obtém template de análise registrado

    Args:
        analysis_type: Tipo de análise
        version: Versão específica (None = mais recente)

    Returns:
        Tupla (template, config)
    """
    template, config = registry.get(analysis_type, version)
    return template, config


def list_available_analyses() -> list[str]:
    """
    Lista todos os tipos de análise disponíveis

    Returns:
        Lista de nomes de análises
    """
    prompts: list[str] = registry.list_prompts()
    return prompts
