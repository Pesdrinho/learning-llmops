"""
Exportador de Banco de Dados

Exporta análises para o banco de dados PostgreSQL.
"""

import json

from llmops_lab.db.connectors import get_async_db
from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


class DBExporter:
    """
    Exporta análises para banco de dados

    Insere análises na tabela analysis.generated_reports
    para consulta e auditoria posterior.
    """

    def __init__(self):
        self.db = get_async_db()

    async def export(
        self,
        ticker: str,
        analysis_type: str,
        content: str,
        metadata: dict,
        cost_usd: float,
        tools_used: list[str],
        request_id: str,
    ) -> tuple[bool, int | str]:
        """
        Exporta análise para banco de dados

        Args:
            ticker: Código da ação
            analysis_type: Tipo de análise
            content: Conteúdo da análise
            metadata: Metadados adicionais
            cost_usd: Custo da análise
            tools_used: Ferramentas utilizadas
            request_id: ID da requisição

        Returns:
            Tupla (success, db_id_or_error)
        """
        try:
            query = """
                INSERT INTO analysis.generated_reports (
                    ticker,
                    analysis_type,
                    content,
                    metadata,
                    cost_usd,
                    tools_used,
                    request_id
                ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)
                RETURNING id
            """

            # Converte metadata dict para JSON string
            metadata_json = json.dumps(metadata) if metadata else "{}"

            db_id = await self.db.fetchval(
                query,
                ticker,
                analysis_type,
                content,
                metadata_json,
                cost_usd,
                tools_used,
                request_id,
            )

            logger.info(f"[DBExporter] Análise salva no banco: ID={db_id}")

            return True, db_id

        except Exception as e:
            error = f"Erro ao salvar no banco: {str(e)}"
            logger.error(f"[DBExporter] {error}", exc_info=True)
            return False, error

    async def get_analysis_by_id(self, analysis_id: int) -> dict | None:
        """
        Busca análise por ID

        Args:
            analysis_id: ID da análise

        Returns:
            Dicionário com dados ou None
        """
        try:
            query = """
                SELECT
                    id,
                    ticker,
                    analysis_type,
                    content,
                    metadata,
                    cost_usd,
                    tools_used,
                    request_id,
                    created_at,
                    updated_at
                FROM analysis.generated_reports
                WHERE id = $1
            """

            row = await self.db.fetchrow(query, analysis_id)

            if not row:
                return None

            return dict(row)

        except Exception as e:
            logger.error(f"[DBExporter] Erro ao buscar análise: {e}", exc_info=True)
            return None

    async def list_analyses(
        self,
        ticker: str | None = None,
        analysis_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """
        Lista análises com filtros

        Args:
            ticker: Filtrar por ticker
            analysis_type: Filtrar por tipo
            limit: Limite de resultados

        Returns:
            Lista de análises
        """
        try:
            conditions: list[str] = []
            params: list[str | int] = []
            param_count = 1

            if ticker:
                conditions.append(f"ticker = ${param_count}")
                params.append(ticker)
                param_count += 1

            if analysis_type:
                conditions.append(f"analysis_type = ${param_count}")
                params.append(analysis_type)
                param_count += 1

            where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

            query = f"""
                SELECT
                    id,
                    ticker,
                    analysis_type,
                    cost_usd,
                    tools_used,
                    request_id,
                    created_at
                FROM analysis.generated_reports
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ${param_count}
            """

            params.append(limit)

            rows = await self.db.fetch(query, *params)

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"[DBExporter] Erro ao listar análises: {e}", exc_info=True)
            return []

    async def get_stats(self) -> dict:
        """
        Obtém estatísticas de análises

        Returns:
            Dicionário com estatísticas
        """
        try:
            query = """
                SELECT
                    COUNT(*) as total_analyses,
                    COUNT(DISTINCT ticker) as unique_tickers,
                    SUM(cost_usd) as total_cost_usd,
                    AVG(cost_usd) as avg_cost_usd,
                    MIN(created_at) as first_analysis,
                    MAX(created_at) as last_analysis
                FROM analysis.generated_reports
            """

            row = await self.db.fetchrow(query)

            return dict(row) if row else {}

        except Exception as e:
            logger.error(f"[DBExporter] Erro ao obter estatísticas: {e}", exc_info=True)
            return {}
