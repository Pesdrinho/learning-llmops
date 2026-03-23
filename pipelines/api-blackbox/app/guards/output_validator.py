"""
Output Validator - Validação de Output do LLM

Valida a estrutura, formato e conteúdo das respostas do LLM
antes de retornar ao cliente.
"""

import json
import re
from typing import Any, Literal

from guards.topic_validator import ValidationResult

from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


class OutputValidator:
    """
    Valida outputs do LLM

    Funcionalidades:
    - Validação de formato (JSON, texto, etc)
    - Validação de campos obrigatórios
    - Sanitização de conteúdo
    - Detecção de informações sensíveis vazadas
    """

    def __init__(
        self,
        expected_format: Literal["text", "json", "json_array"] = "text",
        required_fields: list[str] | None = None,
        max_length: int | None = None,
    ):
        """
        Inicializa o validador de output

        Args:
            expected_format: Formato esperado do output
            required_fields: Lista de campos obrigatórios (para JSON)
            max_length: Tamanho máximo permitido
        """
        self.expected_format = expected_format
        self.required_fields = required_fields or []
        self.max_length = max_length

    def validate(self, output: str, metadata: dict[str, Any] | None = None) -> ValidationResult:
        """
        Valida o output do LLM

        Args:
            output: String de output a validar
            metadata: Metadados adicionais

        Returns:
            ValidationResult com resultado da validação
        """
        if not output or not output.strip():
            return ValidationResult(False, "Output vazio")

        if self.max_length and len(output) > self.max_length:
            return ValidationResult(
                False, f"Output excede tamanho máximo ({len(output)} > {self.max_length})", 0.0
            )

        if self.expected_format in ["json", "json_array"]:
            return self._validate_json(output)

        if self._contains_leaked_info(output):
            return ValidationResult(False, "Output contém informações sensíveis do sistema", 0.0)

        return ValidationResult(True, "Output válido", 1.0)

    def _validate_json(self, output: str) -> ValidationResult:
        """
        Valida output JSON

        Args:
            output: String JSON

        Returns:
            ValidationResult
        """
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError as e:
            logger.warning(f"Output não é JSON válido: {e}")
            return ValidationResult(False, f"Output não é JSON válido: {str(e)}", 0.0)

        if self.expected_format == "json_array":
            if not isinstance(parsed, list):
                return ValidationResult(False, "Output deveria ser um array JSON", 0.0)

        if self.required_fields:
            if isinstance(parsed, list):
                for i, item in enumerate(parsed):
                    if not isinstance(item, dict):
                        continue
                    missing = [f for f in self.required_fields if f not in item]
                    if missing:
                        return ValidationResult(
                            False, f"Item {i} do array está faltando campos: {missing}", 0.3
                        )
            elif isinstance(parsed, dict):
                missing = [f for f in self.required_fields if f not in parsed]
                if missing:
                    return ValidationResult(
                        False, f"Output está faltando campos obrigatórios: {missing}", 0.3
                    )

        return ValidationResult(True, "JSON válido", 1.0)

    def _contains_leaked_info(self, output: str) -> bool:
        """
        Verifica se o output contém informações sensíveis do sistema

        Args:
            output: Texto a verificar

        Returns:
            True se informação sensível detectada
        """
        leak_patterns = [
            r'api[_\s-]?key["\s:=]+[\w-]{20,}',
            r'secret["\s:=]+[\w-]{20,}',
            r'password["\s:=]+[\w-]{8,}',
            r'token["\s:=]+[\w-]{20,}',
            r"<OPENROUTER_API_KEY>",
            r"DB_PASSWORD",
            r"postgresql://.*@",
        ]

        for pattern in leak_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                logger.error(f"Informação sensível detectada no output: pattern={pattern}")
                return True

        return False

    def sanitize(self, output: str) -> str:
        """
        Sanitiza o output removendo conteúdo problemático

        Args:
            output: Texto a sanitizar

        Returns:
            Texto sanitizado
        """
        sanitized = output

        sanitized = re.sub(
            r'api[_\s-]?key["\s:=]+[\w-]{20,}', "[API_KEY_REDACTED]", sanitized, flags=re.IGNORECASE
        )

        sanitized = re.sub(
            r'secret["\s:=]+[\w-]{20,}', "[SECRET_REDACTED]", sanitized, flags=re.IGNORECASE
        )

        sanitized = re.sub(
            r'password["\s:=]+[\w-]{8,}', "[PASSWORD_REDACTED]", sanitized, flags=re.IGNORECASE
        )

        return sanitized

    def extract_json_from_text(self, text: str) -> dict | list | None:
        """
        Tenta extrair JSON de um texto que pode conter outras coisas

        Útil quando o LLM adiciona texto explicativo antes/depois do JSON.

        Args:
            text: Texto contendo JSON

        Returns:
            Objeto Python parseado ou None
        """
        json_pattern = r"\{(?:[^{}]|(?:\{[^{}]*\}))*\}|\[(?:[^\[\]]|(?:\[[^\[\]]*\]))*\]"
        matches = re.findall(json_pattern, text, re.DOTALL)

        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

        return None

    def validate_tool_calls(self, output: dict | list) -> ValidationResult:
        """
        Valida estrutura de tool calls no formato Qwen

        Args:
            output: Dicionário ou lista parseada

        Returns:
            ValidationResult
        """
        if isinstance(output, list):
            items = output
        else:
            items = [output]

        for item in items:
            if not isinstance(item, dict):
                return ValidationResult(False, "Item não é um dicionário")

            if "messages" not in item:
                return ValidationResult(False, "Campo 'messages' ausente")

            messages = item["messages"]
            if not isinstance(messages, list):
                return ValidationResult(False, "'messages' não é uma lista")

            for msg in messages:
                if "role" not in msg or "content" not in msg:
                    return ValidationResult(False, "Mensagem sem 'role' ou 'content'")

                if msg["role"] == "assistant" and "tool_calls" in msg:
                    tool_calls = msg["tool_calls"]
                    if not isinstance(tool_calls, list):
                        return ValidationResult(False, "'tool_calls' não é uma lista")

                    for tc in tool_calls:
                        if "name" not in tc or "arguments" not in tc:
                            return ValidationResult(False, "tool_call sem 'name' ou 'arguments'")

        return ValidationResult(True, "Tool calls válidos", 1.0)


def create_json_validator(
    required_fields: list[str] | None = None, is_array: bool = False
) -> OutputValidator:
    """
    Cria validador pré-configurado para JSON

    Args:
        required_fields: Campos obrigatórios
        is_array: Se espera array ou objeto único

    Returns:
        OutputValidator configurado
    """
    format_type = "json_array" if is_array else "json"
    return OutputValidator(expected_format=format_type, required_fields=required_fields)


def create_dataset_validator() -> OutputValidator:
    """
    Cria validador para datasets de fine-tuning

    Returns:
        OutputValidator configurado para validar datasets
    """
    return OutputValidator(expected_format="json_array", required_fields=["messages"])
