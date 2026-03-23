"""
Ferramenta WebSearch - Busca na Web

Busca informações na web usando DuckDuckGo para complementar análises.
"""

import asyncio
from datetime import datetime

from ddgs import DDGS

from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


class WebSearchTool:
    """
    Ferramenta para busca na web usando DuckDuckGo

    Busca informações relevantes sobre empresas e ações para
    enriquecer análises com contexto atual do mercado.
    """

    def __init__(self):
        self.max_results = 5
        self.timeout_seconds = 10

    async def search(
        self, query: str, max_results: int | None = None
    ) -> tuple[bool, list[dict] | str]:
        """
        Executa busca na web

        Args:
            query: Termo de busca
            max_results: Número máximo de resultados (padrão: 5)

        Returns:
            Tupla (success, results_or_error)
        """
        max_results = max_results or self.max_results

        logger.info(f"Executando busca web: {query}")

        try:
            results = await asyncio.wait_for(
                asyncio.to_thread(self._sync_search, query, max_results),
                timeout=self.timeout_seconds,
            )

            if not results:
                logger.warning("Busca retornou 0 resultados")
                return True, []

            logger.info(f"Busca concluída: {len(results)} resultados")
            return True, results

        except asyncio.TimeoutError:
            error = f"Busca excedeu timeout de {self.timeout_seconds}s"
            logger.error(error)
            return False, error

        except Exception as e:
            error = f"Erro na busca web: {str(e)}"
            logger.error(error, exc_info=True)
            return False, error

    def _sync_search(self, query: str, max_results: int) -> list[dict]:
        """
        Execução síncrona da busca (para rodar em thread)

        Args:
            query: Termo de busca
            max_results: Número máximo de resultados

        Returns:
            Lista de resultados
        """
        try:
            ddgs = DDGS()
            results = list(ddgs.text(query, max_results=max_results))
            return results
        except Exception as e:
            logger.error(f"Erro na busca DuckDuckGo: {e}")
            return []

    def extract_snippets(self, results: list[dict]) -> list[dict]:
        """
        Extrai snippets relevantes dos resultados

        Args:
            results: Lista de resultados da busca

        Returns:
            Lista de snippets processados
        """
        snippets = []

        for result in results:
            snippet = {
                "title": result.get("title", ""),
                "body": result.get("body", ""),
                "url": result.get("href", ""),
            }

            if snippet["title"] or snippet["body"]:
                snippets.append(snippet)

        return snippets

    def format_for_context(self, snippets: list[dict]) -> str:
        """
        Formata snippets para contexto do LLM

        Args:
            snippets: Lista de snippets extraídos

        Returns:
            String formatada para análise
        """
        if not snippets:
            return "Nenhuma informação adicional encontrada na web."

        formatted = "# Informações da Web\n\n"

        for i, snippet in enumerate(snippets, 1):
            formatted += f"## Fonte {i}: {snippet['title']}\n\n"
            formatted += f"{snippet['body']}\n\n"
            formatted += f"**URL**: {snippet['url']}\n\n"
            formatted += "---\n\n"

        return formatted.strip()

    async def search_ticker_info(self, ticker: str) -> dict:
        """
        Busca informações sobre um ticker específico

        Args:
            ticker: Código da ação

        Returns:
            Dicionário com resultados
        """
        start_time = datetime.now()

        query = f"{ticker} B3 ação notícias análise"

        success, result = await self.search(query)

        if not success:
            return {
                "success": False,
                "error": result,
                "ticker": ticker,
                "execution_time_ms": int((datetime.now() - start_time).total_seconds() * 1000),
            }

        if not isinstance(result, list):
            return {
                "success": False,
                "error": "Resultado inválido da busca",
                "ticker": ticker,
                "execution_time_ms": int((datetime.now() - start_time).total_seconds() * 1000),
            }

        snippets = self.extract_snippets(result)
        formatted_context = self.format_for_context(snippets)

        execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        return {
            "success": True,
            "ticker": ticker,
            "query": query,
            "results_count": len(result),
            "snippets": snippets,
            "formatted_context": formatted_context,
            "execution_time_ms": execution_time_ms,
        }

    async def search_market_context(self, ticker: str, analysis_type: str) -> dict:
        """
        Busca contexto de mercado específico para o tipo de análise

        Args:
            ticker: Código da ação
            analysis_type: Tipo de análise

        Returns:
            Dicionário com resultados
        """
        start_time = datetime.now()

        query_map = {
            "price_movement": f"{ticker} preço cotação tendência",
            "volume_analysis": f"{ticker} volume negociação liquidez",
            "trend_analysis": f"{ticker} tendência mercado perspectiva",
            "support_resistance": f"{ticker} suporte resistência análise técnica",
            "comparative_analysis": f"{ticker} comparação setor concorrentes",
        }

        query = query_map.get(analysis_type, f"{ticker} B3 análise")

        success, result = await self.search(query)

        if not success:
            return {
                "success": False,
                "error": result,
                "ticker": ticker,
                "analysis_type": analysis_type,
                "execution_time_ms": int((datetime.now() - start_time).total_seconds() * 1000),
            }

        if not isinstance(result, list):
            return {
                "success": False,
                "error": "Resultado inválido da busca",
                "ticker": ticker,
                "analysis_type": analysis_type,
                "execution_time_ms": int((datetime.now() - start_time).total_seconds() * 1000),
            }

        snippets = self.extract_snippets(result)
        formatted_context = self.format_for_context(snippets)

        execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        return {
            "success": True,
            "ticker": ticker,
            "analysis_type": analysis_type,
            "query": query,
            "results_count": len(result),
            "snippets": snippets,
            "formatted_context": formatted_context,
            "execution_time_ms": execution_time_ms,
        }
