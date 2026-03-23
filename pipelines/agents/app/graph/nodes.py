"""
Nós do Grafo LangGraph

Implementa a lógica de cada nó no grafo de agentes.
"""

from datetime import datetime

from config import get_config
from graph.state import AgentState
from langchain_openai import ChatOpenAI
from prompts.analysis import get_analysis_prompt
from tools.nl2sql import NL2SQLTool
from tools.validators import validate_analysis_output
from tools.websearch import WebSearchTool

from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


async def router_node(state: AgentState) -> AgentState:
    """
    Nó de roteamento - decide quais ferramentas executar

    Args:
        state: Estado atual

    Returns:
        Estado atualizado
    """
    ticker = state.get("ticker", "N/A")
    analysis_type = state.get("analysis_type", "N/A")
    period_days = state.get("period_days", 0)

    logger.info("=" * 80)
    logger.info("[Router] 🎯 Iniciando análise")
    logger.info(f"[Router]   Ticker: {ticker}")
    logger.info(f"[Router]   Tipo: {analysis_type}")
    logger.info(f"[Router]   Período: {period_days} dias")
    logger.info("=" * 80)

    nl2sql_executed = False
    websearch_executed = False
    tools_used = []

    if analysis_type in [
        "price_movement",
        "volume_analysis",
        "trend_analysis",
        "support_resistance",
    ]:
        nl2sql_executed = True
        tools_used.append("nl2sql")

    websearch_executed = True
    tools_used.append("websearch")

    logger.info(f"[Router] 🔧 Ferramentas selecionadas: {', '.join(tools_used)}")

    return {
        "nl2sql_executed": nl2sql_executed,
        "websearch_executed": websearch_executed,
        "tools_used": tools_used,
        "should_retry": False,
        "retry_count": 0,
    }


async def nl2sql_node(state: AgentState) -> AgentState:
    """
    Nó NL2SQL - busca dados históricos

    Args:
        state: Estado atual

    Returns:
        Estado atualizado com apenas as chaves modificadas
    """
    if not state.get("nl2sql_executed"):
        logger.info("[NL2SQL] Pulando (não selecionado)")
        return {"nl2sql_context": "Dados SQL não disponíveis para esta análise."}

    logger.info(f"[NL2SQL] Executando para {state['ticker']}")

    try:
        tool = NL2SQLTool()
        result = await tool.analyze_ticker(state["ticker"], state["period_days"])

        if result["success"]:
            query = result.get("query", "N/A")
            data_points = result.get("data_points", 0)
            raw_data = result.get("raw_data", [])

            logger.info(f"[NL2SQL] ✅ Sucesso: {data_points} pontos de dados")
            logger.info(f"[NL2SQL] 📊 Query executada:\n{query}")

            if raw_data and len(raw_data) > 0:
                logger.info("[NL2SQL] 📋 Primeiras 2 linhas do resultado:")
                for i, row in enumerate(raw_data[:2], 1):
                    logger.info(f"[NL2SQL]   Linha {i}: {dict(row)}")

            return {
                "nl2sql_data": result,
                "nl2sql_context": result["formatted_data"],
            }
        else:
            error_msg = result.get("error", "Erro desconhecido")
            logger.error(f"[NL2SQL] ❌ Erro: {error_msg}")

            return {
                "nl2sql_context": f"Erro ao buscar dados SQL: {error_msg}",
                "errors": [f"NL2SQL: {error_msg}"],
            }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"[NL2SQL] 💥 Exceção: {error_msg}", exc_info=True)

        return {
            "nl2sql_context": f"Erro inesperado ao buscar dados SQL: {error_msg}",
            "errors": [f"NL2SQL: {error_msg}"],
        }


async def websearch_node(state: AgentState) -> AgentState:
    """
    Nó WebSearch - busca informações complementares

    Args:
        state: Estado atual

    Returns:
        Estado atualizado com apenas as chaves modificadas
    """
    if not state.get("websearch_executed"):
        logger.info("[WebSearch] Pulando (não selecionado)")
        return {"websearch_context": "Informações da web não disponíveis para esta análise."}

    logger.info(f"[WebSearch] 🔍 Executando para {state['ticker']}")

    try:
        tool = WebSearchTool()
        result = await tool.search_market_context(state["ticker"], state["analysis_type"])

        if result["success"]:
            results_count = result.get("results_count", 0)
            snippets = result.get("snippets", [])
            query = result.get("query", "N/A")

            logger.info(f"[WebSearch] ✅ Sucesso: {results_count} resultados")
            logger.info(f"[WebSearch] 🔎 Query executada: {query}")

            if snippets and len(snippets) > 0:
                logger.info("[WebSearch] 📰 Resumo dos resultados:")
                for i, snippet in enumerate(snippets[:3], 1):
                    title = snippet.get("title", "N/A")
                    body_preview = snippet.get("body", "")[:100] + "..."
                    logger.info(f"[WebSearch]   {i}. {title}")
                    logger.info(f"[WebSearch]      {body_preview}")

            return {
                "websearch_data": result,
                "websearch_context": result["formatted_context"],
            }
        else:
            error_msg = result.get("error", "Erro desconhecido")
            logger.warning(f"[WebSearch] ⚠️  Erro: {error_msg}")

            return {
                "websearch_context": f"Informações da web não disponíveis: {error_msg}",
                "errors": [f"WebSearch: {error_msg}"],
            }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"[WebSearch] 💥 Exceção: {error_msg}", exc_info=True)

        return {
            "websearch_context": f"Erro inesperado na busca web: {error_msg}",
            "errors": [f"WebSearch: {error_msg}"],
        }


async def synthesis_node(state: AgentState) -> AgentState:
    """
    Nó de síntese - gera análise final com LLM

    Args:
        state: Estado atual

    Returns:
        Estado atualizado
    """
    ticker = state.get("ticker", "N/A")
    analysis_type = state.get("analysis_type", "N/A")

    logger.info(f"[Synthesis] 🤖 Gerando análise para {ticker}")

    start_time = datetime.now()

    try:
        config = get_config()

        api_key = config.openrouter_api_key
        if not api_key or (isinstance(api_key, str) and not api_key.strip()):
            error_msg = "OPENROUTER_API_KEY não configurada. Configure via variável de ambiente ou GCP Secret Manager."
            logger.error(f"[Synthesis] ❌ {error_msg}")
            return {
                "analysis_content": f"Erro de configuração: {error_msg}",
                "errors": [f"Synthesis: {error_msg}"],
                "cost_usd": 0.0,
            }

        # Configura LLM para usar OpenRouter
        llm = ChatOpenAI(
            model=config.llm_model,
            temperature=config.llm_temperature,
            max_tokens=config.llm_max_tokens,
            api_key=api_key,
            base_url=config.openrouter_base_url,
        )

        template, prompt_config = get_analysis_prompt(analysis_type)

        nl2sql_ctx = state.get("nl2sql_context", "N/A")
        websearch_ctx = state.get("websearch_context", "N/A")

        logger.info(f"[Synthesis] 📝 Contexto NL2SQL: {len(nl2sql_ctx)} chars")
        logger.info(f"[Synthesis] 🌐 Contexto WebSearch: {len(websearch_ctx)} chars")

        formatted_prompt = template.format_messages(
            ticker=ticker,
            period_days=state.get("period_days", 90),
            nl2sql_context=nl2sql_ctx,
            websearch_context=websearch_ctx,
        )

        response = await llm.ainvoke(formatted_prompt)

        analysis_content = response.content
        execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        usage = getattr(response, "usage_metadata", None) or getattr(
            response, "response_metadata", {}
        ).get("token_usage", {})
        prompt_tokens = usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0) or usage.get("completion_tokens", 0)

        cost_input = prompt_tokens * 0.00015 / 1000
        cost_output = completion_tokens * 0.00060 / 1000
        cost_usd = cost_input + cost_output

        logger.info("[Synthesis] ✅ Análise gerada:")
        logger.info(f"[Synthesis]   Tamanho: {len(analysis_content)} chars")
        logger.info(
            f"[Synthesis]   Tokens: {prompt_tokens} in + {completion_tokens} out = {prompt_tokens + completion_tokens} total"
        )
        logger.info(f"[Synthesis]   Custo: ${cost_usd:.6f}")
        logger.info(f"[Synthesis]   Latência: {execution_time_ms}ms")

        return {
            "analysis_content": analysis_content,
            "cost_usd": cost_usd,
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"[Synthesis] 💥 Erro: {error_msg}", exc_info=True)

        return {
            "analysis_content": f"Erro ao gerar análise: {error_msg}",
            "errors": [f"Synthesis: {error_msg}"],
            "cost_usd": 0.0,
        }


async def validation_node(state: AgentState) -> AgentState:
    """
    Nó de validação - valida qualidade da análise

    Args:
        state: Estado atual

    Returns:
        Estado atualizado
    """
    logger.info("[Validation] 🔍 Validando análise")

    content = state.get("analysis_content", "")
    content_length = len(content)

    logger.info(f"[Validation] 📏 Tamanho do conteúdo: {content_length} chars")

    is_valid, error_msg = validate_analysis_output(content)

    validation_result = {"is_valid": is_valid, "error": error_msg}

    if not is_valid:
        logger.warning(f"[Validation] ❌ Falhou: {error_msg}")

        retry_count = state.get("retry_count", 0)
        max_retries = get_config().max_retry_attempts

        if retry_count < max_retries:
            new_retry_count = retry_count + 1
            logger.info(f"[Validation] 🔄 Tentando novamente ({new_retry_count}/{max_retries})")

            return {
                "validation_result": validation_result,
                "should_retry": True,
                "retry_count": new_retry_count,
            }
        else:
            logger.error("[Validation] 🚫 Máximo de tentativas atingido")

            return {
                "validation_result": validation_result,
                "should_retry": False,
                "errors": [f"Validação: {error_msg} (após {max_retries} tentativas)"],
            }
    else:
        logger.info("[Validation] ✅ Validação passou")

        return {
            "validation_result": validation_result,
            "should_retry": False,
        }


async def end_node(state: AgentState) -> AgentState:
    """
    Nó final - finaliza execução

    Args:
        state: Estado atual

    Returns:
        Estado atualizado
    """
    ticker = state.get("ticker", "N/A")
    errors = state.get("errors", [])
    tools_used = state.get("tools_used", [])
    cost_usd = state.get("cost_usd", 0.0)

    # Garante que tools_used é uma lista de strings
    if tools_used and isinstance(tools_used, list):
        tools_used_str = ", ".join(str(t) for t in tools_used if t)
    else:
        tools_used_str = "nenhuma"

    logger.info("=" * 80)
    logger.info(f"[End] 🏁 Análise concluída para {ticker}")
    logger.info(f"[End]   Ferramentas usadas: {tools_used_str}")
    logger.info(f"[End]   Custo total: ${cost_usd:.6f}")

    if errors:
        logger.warning(f"[End] ⚠️  Erros durante execução ({len(errors)}):")
        for i, error in enumerate(errors, 1):
            logger.warning(f"[End]   {i}. {error}")
    else:
        logger.info("[End] ✅ Execução sem erros")

    logger.info("=" * 80)

    return {"should_retry": False}
