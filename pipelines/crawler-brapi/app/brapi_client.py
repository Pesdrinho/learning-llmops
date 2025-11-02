"""
Cliente HTTP para Brapi API
"""

import os
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from llmops_lab.logging.logger import get_logger
from llmops_lab.secrets.manager import get_secret

logger = get_logger(__name__)


class BrapiClient:
    """Cliente HTTP para interagir com a Brapi API"""

    BASE_URL = "https://brapi.dev/api"

    def __init__(self, api_token: str | None = None, timeout: int = 30, max_retries: int = 3):
        """
        Inicializa cliente Brapi

        Args:
            api_token: Token da API (opcional para endpoints públicos)
            timeout: Timeout em segundos
            max_retries: Número máximo de tentativas
        """
        self.api_token = api_token or os.getenv("BRAPI_TOKEN")
        self.timeout = timeout
        self.max_retries = max_retries

        # Headers padrão
        self.headers = {"User-Agent": "LLMOps-Lab-Crawler/0.1.0"}

        if self.api_token:
            self.headers["Authorization"] = f"Bearer {self.api_token}"

        # Cliente HTTP
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        """Context manager enter"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.close()

    async def connect(self):
        """Cria cliente HTTP"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers=self.headers,
                timeout=self.timeout,
            )
            logger.info("Cliente Brapi conectado")

    async def close(self):
        """Fecha cliente HTTP"""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("Cliente Brapi fechado")

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True
    )
    async def _request(
        self, method: str, endpoint: str, params: dict | None = None, **kwargs
    ) -> dict[str, Any]:
        """
        Faz request HTTP com retry

        Args:
            method: Método HTTP (GET, POST, etc)
            endpoint: Endpoint da API
            params: Query parameters
            **kwargs: Argumentos adicionais para httpx

        Returns:
            Resposta JSON
        """
        if not self._client:
            await self.connect()

        try:
            response = await self._client.request(
                method=method, url=endpoint, params=params, **kwargs
            )
            response.raise_for_status()

            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise

    async def get(self, endpoint: str, params: dict | None = None) -> dict[str, Any]:
        """Faz GET request"""
        return await self._request("GET", endpoint, params=params)

    # ========== Métodos específicos da API ==========

    async def get_available_tickers(
        self, search: str | None = None, sector: str | None = None, limit: int = 100
    ) -> dict[str, Any]:
        """
        Lista tickers disponíveis

        Args:
            search: Termo de busca
            sector: Filtro por setor
            limit: Limite de resultados

        Returns:
            Lista de tickers
        """
        params = {"limit": limit}
        if search:
            params["search"] = search
        if sector:
            params["sector"] = sector

        return await self.get("/available", params=params)

    async def get_quote(self, tickers: list[str]) -> dict[str, Any]:
        """
        Obtém cotação atual de tickers

        Args:
            tickers: Lista de tickers (ex: ['PETR4', 'VALE3'])

        Returns:
            Dados de cotação
        """
        tickers_str = ",".join(tickers)
        return await self.get(f"/quote/{tickers_str}")

    async def get_quote_list(
        self, sortBy: str = "volume", sortOrder: str = "desc", limit: int = 10
    ) -> dict[str, Any]:
        """
        Lista cotações ordenadas

        Args:
            sortBy: Campo para ordenação
            sortOrder: Ordem (asc/desc)
            limit: Limite de resultados

        Returns:
            Lista de cotações
        """
        params = {"sortBy": sortBy, "sortOrder": sortOrder, "limit": limit}
        return await self.get("/quote/list", params=params)

    async def get_historical_data(
        self,
        ticker: str,
        range: str = "1mo",
        interval: str = "1d",
        fundamental: bool = False,
        dividends: bool = False,
    ) -> dict[str, Any]:
        """
        Obtém dados históricos (OHLCV)

        Args:
            ticker: Ticker do ativo
            range: Período (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Granularidade (1d, 5d, 1wk, 1mo, 3mo)
            fundamental: Incluir dados fundamentais
            dividends: Incluir dividendos

        Returns:
            Dados históricos
        """
        params = {
            "range": range,
            "interval": interval,
            "fundamental": str(fundamental).lower(),
            "dividends": str(dividends).lower(),
        }
        return await self.get(f"/quote/{ticker}", params=params)

    async def get_currency(self, currency: str) -> dict[str, Any]:
        """
        Obtém taxa de câmbio

        Args:
            currency: Par de moedas (ex: 'USD-BRL', 'EUR-USD')

        Returns:
            Taxa de câmbio
        """
        return await self.get("/v2/currency", params={"currency": currency})

    async def get_available_currencies(self) -> dict[str, Any]:
        """Lista moedas disponíveis"""
        return await self.get("/v2/currency/available")

    async def get_crypto(self, coin: str | None = None, currency: str = "BRL") -> dict[str, Any]:
        """
        Obtém preços de criptomoedas

        Args:
            coin: Símbolo da cripto (ex: 'BTC', 'ETH')
            currency: Moeda de referência

        Returns:
            Preços de cripto
        """
        params = {"currency": currency}
        if coin:
            params["coin"] = coin

        return await self.get("/v2/crypto", params=params)

    async def get_inflation(
        self,
        country: str = "brazil",
        start: str | None = None,
        end: str | None = None,
        sortOrder: str = "desc",
    ) -> dict[str, Any]:
        """
        Obtém dados de inflação (IPCA)

        Args:
            country: País (brazil)
            start: Data início (DD/MM/YYYY)
            end: Data fim (DD/MM/YYYY)
            sortOrder: Ordem (asc/desc)

        Returns:
            Dados de inflação
        """
        params = {"sortOrder": sortOrder}
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        return await self.get("/v2/inflation", params=params)

    async def get_prime_rate(
        self,
        country: str = "brazil",
        start: str | None = None,
        end: str | None = None,
        sortOrder: str = "desc",
    ) -> dict[str, Any]:
        """
        Obtém dados da taxa SELIC

        Args:
            country: País (brazil)
            start: Data início (DD/MM/YYYY)
            end: Data fim (DD/MM/YYYY)
            sortOrder: Ordem (asc/desc)

        Returns:
            Dados da SELIC
        """
        params = {"sortOrder": sortOrder}
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        return await self.get("/v2/prime-rate", params=params)

    async def health_check(self) -> bool:
        """
        Verifica saúde da API

        Returns:
            True se API está respondendo
        """
        try:
            await self.get_available_currencies()
            logger.info("Brapi API está saudável")
            return True
        except Exception as e:
            logger.error(f"Brapi API com problemas: {e}")
            return False


# Função helper para criar cliente
async def get_brapi_client() -> BrapiClient:
    """Cria e retorna cliente Brapi"""
    token = None
    try:
        token = get_secret("BRAPI_TOKEN", default=None)
    except Exception:
        logger.warning("BRAPI_TOKEN não configurado, usando endpoints públicos")

    client = BrapiClient(api_token=token)
    await client.connect()
    return client
