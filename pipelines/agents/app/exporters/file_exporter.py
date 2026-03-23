"""
Exportador de Arquivos

Exporta análises para arquivos markdown no sistema de arquivos.
"""

import os
from datetime import datetime
from pathlib import Path

from config import get_config
from google.cloud import storage

from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


def _resolve_credentials_path(creds_path: str) -> Path:
    """
    Resolve caminho de credenciais, suportando caminhos relativos e absolutos

    Se o caminho for relativo, procura a partir da raiz do projeto (/app)
    Se for absoluto, usa diretamente

    Args:
        creds_path: Caminho do arquivo de credenciais

    Returns:
        Path resolvido
    """
    creds_file = Path(creds_path)

    # Se já é absoluto, retorna direto
    if creds_file.is_absolute():
        return creds_file

    # Remove prefixos relativos como ./ e normaliza o caminho
    normalized_path = creds_path.lstrip("./")

    # Remove "app/" do início se presente (pode estar no .env como ./app/.gcp/...)
    if normalized_path.startswith("app/"):
        normalized_path = normalized_path[4:]  # Remove "app/"

    # Procura a raiz do projeto (/app) subindo a partir do diretório atual
    current = Path.cwd()

    for _ in range(5):
        # Verifica se encontrou a raiz do projeto
        # A raiz pode ser identificada por:
        # 1. Ter um arquivo .env
        # 2. Ser o diretório /app (no Docker)
        # 3. Ter um diretório .gcp (onde ficam as credenciais)
        is_root = (
            (current / ".env").exists() or current.name == "app" or (current / ".gcp").exists()
        )

        if is_root:
            # Encontrou a raiz, resolve o caminho relativo a partir dela
            resolved = current / normalized_path

            if resolved.exists():
                return resolved.resolve()

            # Se não existe mas encontrou a raiz, retorna o caminho resolvido
            # para que o erro seja claro sobre onde estava procurando
            return resolved.resolve()

        # Tenta encontrar o arquivo relativo a este diretório (fallback)
        resolved = current / normalized_path
        if resolved.exists():
            return resolved.resolve()

        parent = current.parent
        if parent == current:  # Chegou na raiz do sistema
            break
        current = parent

    # Se não encontrou a raiz, tenta relativo ao diretório atual
    return (Path.cwd() / normalized_path).resolve()


class FileExporter:
    """
    Exporta análises para arquivos markdown

    Cria estrutura organizada por data e salva análises
    em formato markdown para consumo posterior.
    """

    def __init__(self):
        self.config = get_config()
        self.base_dir = Path(self.config.exports_dir)
        self.gcs_bucket_name = os.getenv("GCS_RAG_DOCS_BUCKET", "llmops_rag_docs")

    def _ensure_directory(self, directory: Path) -> None:
        """
        Garante que diretório existe

        Args:
            directory: Caminho do diretório
        """
        directory.mkdir(parents=True, exist_ok=True)

    def _generate_filename(self, ticker: str, analysis_type: str, timestamp: datetime) -> str:
        """
        Gera nome de arquivo para análise

        Args:
            ticker: Código da ação
            analysis_type: Tipo de análise
            timestamp: Timestamp da análise

        Returns:
            Nome do arquivo
        """
        date_str = timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"{ticker}_{analysis_type}_{date_str}.md"
        return filename

    def _format_metadata_section(self, metadata: dict) -> str:
        """
        Formata seção de metadados

        Args:
            metadata: Dicionário de metadados

        Returns:
            String formatada
        """
        lines = ["---", "# Metadados da Análise", ""]

        for key, value in metadata.items():
            if key == "tools_used" and isinstance(value, list):
                lines.append(f"**{key}**: {', '.join(value)}")
            else:
                lines.append(f"**{key}**: {value}")

        lines.append("")
        lines.append("---")
        lines.append("")

        return "\n".join(lines)

    def _upload_to_gcs(
        self, source_file_path: Path, destination_blob_name: str
    ) -> tuple[bool, str]:
        """
        Faz upload de arquivo para Google Cloud Storage

        Args:
            source_file_path: Caminho do arquivo local
            destination_blob_name: Nome do blob no bucket

        Returns:
            Tupla (success, message_or_error)
        """
        try:
            # Verifica se está rodando no Cloud Run (usa ADC automaticamente)
            is_cloud_run = os.getenv("K_SERVICE") is not None

            # Verifica credenciais para desenvolvimento local
            if not is_cloud_run:
                creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                if creds_path:
                    creds_file = _resolve_credentials_path(creds_path)
                    if not creds_file.exists():
                        error_msg = (
                            f"Arquivo de credenciais não encontrado: {creds_path}\n"
                            f"Caminho resolvido: {creds_file}\n"
                            f"Diretório atual: {os.getcwd()}\n"
                            f"Para desenvolvimento local, você precisa:\n"
                            f"1. Baixar o JSON da Service Account do GCP\n"
                            f"2. Configurar GOOGLE_APPLICATION_CREDENTIALS no .env (relativo à raiz do projeto ou absoluto)\n"
                            f"3. Ou remover GOOGLE_APPLICATION_CREDENTIALS se estiver usando gcloud auth application-default login"
                        )
                        logger.error(f"[FileExporter] {error_msg}")
                        return False, error_msg

                    # Atualiza a variável de ambiente com o caminho absoluto resolvido
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(creds_file)
                    logger.debug(f"[FileExporter] Usando credenciais de: {creds_file}")
                else:
                    logger.debug(
                        "[FileExporter] Tentando usar Application Default Credentials (gcloud auth)"
                    )

            storage_client = storage.Client()
            bucket = storage_client.bucket(self.gcs_bucket_name)
            blob = bucket.blob(destination_blob_name)

            generation_match_precondition = 0
            blob.upload_from_filename(
                str(source_file_path), if_generation_match=generation_match_precondition
            )

            gcs_path = f"gs://{self.gcs_bucket_name}/{destination_blob_name}"
            logger.info(
                f"[FileExporter] Arquivo enviado para GCS: {source_file_path.name} -> {gcs_path}"
            )

            return True, gcs_path

        except Exception as e:
            error_str = str(e)

            # Mensagem de erro mais clara para problemas de autenticação
            if "DefaultCredentialsError" in error_str or "was not found" in error_str:
                error_msg = (
                    f"Erro de autenticação GCP: {error_str}\n"
                    f"Para desenvolvimento local, configure uma das opções:\n"
                    f"1. GOOGLE_APPLICATION_CREDENTIALS apontando para arquivo JSON válido\n"
                    f"2. Execute: gcloud auth application-default login\n"
                    f"3. No Cloud Run, certifique-se de que o Service Account tem permissão 'Storage Object Admin'"
                )
            else:
                error_msg = f"Erro ao enviar para GCS: {error_str}"

            logger.error(f"[FileExporter] {error_msg}", exc_info=True)
            return False, error_msg

    async def export(
        self,
        ticker: str,
        analysis_type: str,
        content: str,
        metadata: dict,
    ) -> tuple[bool, str]:
        """
        Exporta análise para arquivo

        Args:
            ticker: Código da ação
            analysis_type: Tipo de análise
            content: Conteúdo da análise
            metadata: Metadados adicionais

        Returns:
            Tupla (success, file_path_or_error)
        """
        try:
            timestamp = datetime.now()

            date_dir = self.base_dir / timestamp.strftime("%Y-%m-%d")
            self._ensure_directory(date_dir)

            filename = self._generate_filename(ticker, analysis_type, timestamp)
            file_path = date_dir / filename

            metadata_section = self._format_metadata_section(metadata)

            full_content = f"{metadata_section}\n{content}\n"

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(full_content)

            logger.info(f"[FileExporter] Análise exportada: {file_path}")

            date_str = timestamp.strftime("%Y-%m-%d")
            destination_blob_name = f"analyses/{date_str}/{filename}"
            gcs_success, gcs_result = self._upload_to_gcs(file_path, destination_blob_name)

            if not gcs_success:
                logger.warning(f"[FileExporter] Falha ao enviar para GCS: {gcs_result}")

            return True, str(file_path)

        except Exception as e:
            error = f"Erro ao exportar arquivo: {str(e)}"
            logger.error(f"[FileExporter] {error}", exc_info=True)
            return False, error

    async def list_exports(self, ticker: str | None = None) -> list[dict]:
        """
        Lista análises exportadas

        Args:
            ticker: Filtrar por ticker (opcional)

        Returns:
            Lista de análises com metadados
        """
        try:
            if not self.base_dir.exists():
                return []

            exports = []

            for date_dir in sorted(self.base_dir.iterdir(), reverse=True):
                if not date_dir.is_dir():
                    continue

                for file_path in date_dir.glob("*.md"):
                    if ticker and not file_path.name.startswith(ticker):
                        continue

                    stat = file_path.stat()

                    exports.append(
                        {
                            "file_path": str(file_path),
                            "filename": file_path.name,
                            "size_bytes": stat.st_size,
                            "created_at": datetime.fromtimestamp(stat.st_ctime),
                            "modified_at": datetime.fromtimestamp(stat.st_mtime),
                        }
                    )

            return exports

        except Exception as e:
            logger.error(f"[FileExporter] Erro ao listar exports: {e}", exc_info=True)
            return []

    async def read_export(self, file_path: str) -> tuple[bool, str]:
        """
        Lê conteúdo de uma análise exportada

        Args:
            file_path: Caminho do arquivo

        Returns:
            Tupla (success, content_or_error)
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            logger.info(f"[FileExporter] Análise lida: {file_path}")
            return True, content

        except Exception as e:
            error = f"Erro ao ler arquivo: {str(e)}"
            logger.error(f"[FileExporter] {error}", exc_info=True)
            return False, error
