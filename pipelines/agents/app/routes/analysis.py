"""
Rota de Análise

Endpoint principal para geração de análises de ações usando agentes.
"""

import json
import time
import uuid
from datetime import datetime

from exporters.db_exporter import DBExporter
from exporters.file_exporter import FileExporter
from fastapi import APIRouter, HTTPException, status
from graph.builder import get_agent_graph
from graph.state import AgentState
from models import AnalysisRequest, AnalysisResponse

from llmops_lab.db.connectors import get_async_db
from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/generate_analysis",
    response_model=AnalysisResponse,
    summary="Gerar análise de ação",
    description="Gera análise completa de uma ação usando agentes com NL2SQL e WebSearch",
)
async def generate_analysis(request: AnalysisRequest):
    """
    Endpoint principal - Geração de análise

    Processo completo:
    1. Valida requisição
    2. Inicializa estado do agente
    3. Executa grafo LangGraph
    4. Exporta resultados (arquivo + banco)
    5. Registra logs
    6. Retorna resposta

    Args:
        request: AnalysisRequest com ticker, tipo e período

    Returns:
        AnalysisResponse com análise e metadados

    Raises:
        HTTPException 400: Request inválido
        HTTPException 500: Erro no processamento
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())

    logger.info(
        f"[{request_id}] Gerando análise | "
        f"Ticker: {request.ticker} | "
        f"Tipo: {request.analysis_type} | "
        f"Período: {request.period_days} dias"
    )

    try:
        initial_state: AgentState = {
            "ticker": request.ticker,
            "analysis_type": request.analysis_type,
            "period_days": request.period_days,
            "user_id": request.user_id,
            "request_id": request_id,
            "tools_used": [],
            "errors": [],
            "nl2sql_context": "",
            "websearch_context": "",
            "analysis_content": "",
            "cost_usd": 0.0,
            "total_execution_time_ms": 0,
            "nl2sql_executed": False,
            "websearch_executed": False,
            "should_retry": False,
            "retry_count": 0,
            "validation_result": {},
        }

        graph = get_agent_graph()

        logger.info(f"[{request_id}] Executando grafo de agentes")
        final_state = await graph.ainvoke(initial_state)

        latency_ms = int((time.time() - start_time) * 1000)
        final_state["total_execution_time_ms"] = latency_ms

        if final_state.get("errors"):
            logger.warning(f"[{request_id}] Erros durante execução: {final_state['errors']}")

        file_exporter = FileExporter()
        db_exporter = DBExporter()

        export_metadata = {
            "ticker": final_state["ticker"],
            "analysis_type": final_state["analysis_type"],
            "period_days": final_state["period_days"],
            "tools_used": final_state["tools_used"],
            "cost_usd": final_state["cost_usd"],
            "latency_ms": latency_ms,
            "request_id": request_id,
            "errors": final_state.get("errors", []),
        }

        file_success, file_path_or_error = await file_exporter.export(
            ticker=final_state["ticker"],
            analysis_type=final_state["analysis_type"],
            content=final_state["analysis_content"],
            metadata=export_metadata,
        )

        db_success, db_id_or_error = await db_exporter.export(
            ticker=final_state["ticker"],
            analysis_type=final_state["analysis_type"],
            content=final_state["analysis_content"],
            metadata=export_metadata,
            cost_usd=final_state["cost_usd"],
            tools_used=final_state["tools_used"],
            request_id=request_id,
        )

        export_paths = {}

        if file_success:
            export_paths["file_path"] = file_path_or_error
        else:
            logger.error(f"[{request_id}] Erro ao exportar arquivo: {file_path_or_error}")
            export_paths["file_error"] = file_path_or_error

        if db_success:
            export_paths["db_id"] = db_id_or_error
        else:
            logger.error(f"[{request_id}] Erro ao exportar para banco: {db_id_or_error}")
            export_paths["db_error"] = db_id_or_error

        db = get_async_db()

        log_query = """
            INSERT INTO observability.llm_logs (
                user_id, model, provider, architecture,
                prompt_masked, response_masked,
                input_tokens, output_tokens, cost_usd,
                latency_ms, status, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb)
        """

        prompt_summary = f"Análise {final_state['analysis_type']} de {final_state['ticker']} ({final_state['period_days']} dias)"
        response_summary = (
            final_state["analysis_content"][:500] + "..."
            if len(final_state["analysis_content"]) > 500
            else final_state["analysis_content"]
        )

        metadata_dict = {
            "request_id": request_id,
            "ticker": final_state["ticker"],
            "analysis_type": final_state["analysis_type"],
            "period_days": final_state["period_days"],
            "tools_used": final_state["tools_used"],
            "errors": final_state.get("errors", []),
        }

        # Converte metadata dict para JSON string
        metadata_json = json.dumps(metadata_dict)

        async with db.pool.acquire() as conn:
            await conn.execute(
                log_query,
                request.user_id or "anonymous",
                "openai/gpt-4o-mini",
                "openrouter",
                "agents",
                prompt_summary,
                response_summary,
                0,
                0,
                final_state["cost_usd"],
                latency_ms,
                "success" if not final_state.get("errors") else "success_with_errors",
                metadata_json,
            )

        logger.info(
            f"[{request_id}] Análise concluída | "
            f"Custo: ${final_state['cost_usd']:.6f} | "
            f"Latência: {latency_ms}ms | "
            f"Ferramentas: {', '.join(final_state['tools_used'])}"
        )

        return AnalysisResponse(
            ticker=final_state["ticker"],
            analysis_type=final_state["analysis_type"],
            content=final_state["analysis_content"],
            tools_used=final_state["tools_used"],
            cost_usd=final_state["cost_usd"],
            latency_ms=latency_ms,
            request_id=request_id,
            export_paths=export_paths,
            created_at=datetime.now(),
        )

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)

        logger.error(f"[{request_id}] Erro ao gerar análise: {e}", exc_info=True)

        try:
            db = get_async_db()

            log_query = """
                INSERT INTO observability.llm_logs (
                    user_id, model, provider, architecture,
                    prompt_masked, response_masked,
                    latency_ms, status, error_message
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """

            async with db.pool.acquire() as conn:
                await conn.execute(
                    log_query,
                    request.user_id or "anonymous",
                    "openai/gpt-4o-mini",
                    "openrouter",
                    "agents",
                    f"Análise {request.analysis_type} de {request.ticker}",
                    "Erro durante processamento",
                    latency_ms,
                    "error",
                    str(e),
                )
        except Exception as log_error:
            logger.error(f"Erro ao registrar log de erro: {log_error}")
            pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao gerar análise: {str(e)}",
        ) from e


@router.get(
    "/analyses",
    summary="Listar análises",
    description="Lista análises geradas com filtros opcionais",
)
async def list_analyses(
    ticker: str | None = None, analysis_type: str | None = None, limit: int = 50
):
    """
    Lista análises geradas

    Args:
        ticker: Filtrar por ticker (opcional)
        analysis_type: Filtrar por tipo (opcional)
        limit: Limite de resultados (padrão: 50)

    Returns:
        Lista de análises
    """
    try:
        db_exporter = DBExporter()
        analyses = await db_exporter.list_analyses(ticker, analysis_type, limit)

        return {"analyses": analyses, "total": len(analyses)}

    except Exception as e:
        logger.error(f"Erro ao listar análises: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao listar análises: {str(e)}",
        ) from e


@router.get(
    "/analyses/{analysis_id}",
    summary="Buscar análise por ID",
    description="Retorna análise específica por ID",
)
async def get_analysis(analysis_id: int):
    """
    Busca análise por ID

    Args:
        analysis_id: ID da análise

    Returns:
        Dados da análise
    """
    try:
        db_exporter = DBExporter()
        analysis = await db_exporter.get_analysis_by_id(analysis_id)

        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Análise {analysis_id} não encontrada",
            )

        return analysis

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar análise: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar análise: {str(e)}",
        ) from e


@router.get(
    "/stats",
    summary="Estatísticas de análises",
    description="Retorna estatísticas gerais das análises geradas",
)
async def get_stats():
    """
    Obtém estatísticas de análises

    Returns:
        Estatísticas gerais
    """
    try:
        db_exporter = DBExporter()
        stats = await db_exporter.get_stats()

        return stats

    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter estatísticas: {str(e)}",
        ) from e
