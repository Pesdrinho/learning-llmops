"""
Injection Detector - Detecção de Prompt Injection

Protege contra tentativas de manipular o comportamento do LLM
através de prompt injection attacks.
"""

import re
from typing import Any

from guards.topic_validator import ValidationResult

from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


class InjectionDetector:
    """
    Detecta tentativas de prompt injection

    Estratégias:
    - Patterns conhecidos de injection
    - Detecção de tentativas de role switching
    - Caracteres especiais suspeitos
    - Comandos de sistema
    """

    def __init__(self, strict_mode: bool = False):
        """
        Inicializa o detector de injection

        Args:
            strict_mode: Se True, usa detecção mais agressiva
        """
        self.strict_mode = strict_mode
        self.injection_patterns = self._compile_patterns()

    def _compile_patterns(self) -> list[tuple[re.Pattern, str, float]]:
        """
        Compila padrões regex para detecção

        Returns:
            Lista de tuplas (pattern, description, severity)
            severity: 0.0-1.0 (0.0 = crítico, 1.0 = suspeito)
        """
        patterns = [
            (
                re.compile(
                    r"ignore\s+(previous|all|above)\s+(instructions|rules|prompts?)", re.IGNORECASE
                ),
                "Tentativa de ignorar instruções anteriores",
                0.0,
            ),
            (
                re.compile(r"you\s+are\s+now\s+(?:a|an)\s+\w+", re.IGNORECASE),
                "Tentativa de redefinir papel do assistente",
                0.1,
            ),
            (
                re.compile(r"(?:system|admin|root|developer)\s*[:]\s*", re.IGNORECASE),
                "Tentativa de role switching",
                0.0,
            ),
            (
                re.compile(r"<\|(?:im_start|im_end)\|>", re.IGNORECASE),
                "Tentativa de injetar tokens especiais",
                0.0,
            ),
            (re.compile(r"<\|system\|>", re.IGNORECASE), "Tentativa de injetar role system", 0.0),
            (
                re.compile(
                    r"repeat\s+(?:the|your)\s+(?:prompt|instructions|system\s+message)",
                    re.IGNORECASE,
                ),
                "Tentativa de extrair prompt do sistema",
                0.2,
            ),
            (
                re.compile(
                    r"what\s+(?:are|is)\s+your\s+(?:instructions|rules|system\s+prompt)",
                    re.IGNORECASE,
                ),
                "Tentativa de extrair configuração",
                0.3,
            ),
            (
                re.compile(r"forget\s+(?:everything|all|previous)", re.IGNORECASE),
                "Tentativa de resetar contexto",
                0.1,
            ),
            (
                re.compile(r"disregard\s+(?:all|previous|above)", re.IGNORECASE),
                "Tentativa de desconsiderar instruções",
                0.0,
            ),
            (
                re.compile(r"\[SYSTEM\]|\[ADMIN\]|\[ROOT\]", re.IGNORECASE),
                "Tentativa de simular mensagem de sistema",
                0.0,
            ),
            (
                re.compile(r"<script|javascript:|onerror=|onload=", re.IGNORECASE),
                "Tentativa de XSS/script injection",
                0.0,
            ),
        ]

        if self.strict_mode:
            patterns.extend(
                [
                    (
                        re.compile(r"(\b\w+\s+){50,}", re.IGNORECASE),
                        "Texto excessivamente longo (possível flooding)",
                        0.5,
                    ),
                    (re.compile(r"[^\x00-\x7F]{100,}"), "Excesso de caracteres não-ASCII", 0.7),
                ]
            )

        return patterns

    def validate(self, text: str, metadata: dict[str, Any] | None = None) -> ValidationResult:
        """
        Valida se o texto contém tentativas de injection

        Args:
            text: Texto a validar
            metadata: Metadados adicionais (opcional)

        Returns:
            ValidationResult com resultado da validação
        """
        if not text or not text.strip():
            return ValidationResult(False, "Texto vazio")

        detected_injections = []
        min_severity = 1.0

        for pattern, description, severity in self.injection_patterns:
            if pattern.search(text):
                detected_injections.append({"description": description, "severity": severity})
                min_severity = min(min_severity, severity)
                logger.warning(
                    f"Possível injection detectado: {description} | Severidade: {severity}"
                )

        if detected_injections:
            if min_severity < 0.5:
                return ValidationResult(
                    False,
                    f"Tentativa de prompt injection detectada: {detected_injections[0]['description']}",
                    min_severity,
                )
            else:
                logger.info(f"Padrão suspeito detectado mas permitido: {detected_injections}")

        if self._check_encoding_anomalies(text):
            return ValidationResult(
                False, "Anomalias de encoding detectadas (possível tentativa de bypass)", 0.2
            )

        return ValidationResult(True, "Nenhuma tentativa de injection detectada", 1.0)

    def _check_encoding_anomalies(self, text: str) -> bool:
        """
        Verifica anomalias de encoding que podem indicar bypass

        Args:
            text: Texto a verificar

        Returns:
            True se anomalias detectadas
        """
        null_bytes = text.count("\x00")
        if null_bytes > 0:
            logger.warning(f"Null bytes detectados: {null_bytes}")
            return True

        unicode_overlong = re.search(r"[\uFDD0-\uFDEF]", text)
        if unicode_overlong:
            logger.warning("Caracteres Unicode não-válidos detectados")
            return True

        return False

    def add_pattern(self, pattern: str, description: str, severity: float = 0.0) -> None:
        """
        Adiciona um novo padrão de detecção

        Args:
            pattern: Regex pattern
            description: Descrição da ameaça
            severity: Severidade (0.0 = crítico, 1.0 = suspeito)
        """
        compiled_pattern = re.compile(pattern, re.IGNORECASE)
        self.injection_patterns.append((compiled_pattern, description, severity))
        logger.info(f"Novo padrão adicionado: {description}")

    def get_detected_patterns(self, text: str) -> list[dict]:
        """
        Retorna lista de padrões detectados sem bloquear

        Útil para análise e métricas.

        Args:
            text: Texto a analisar

        Returns:
            Lista de padrões detectados com metadados
        """
        detected = []

        for pattern, description, severity in self.injection_patterns:
            matches = pattern.findall(text)
            if matches:
                detected.append(
                    {
                        "description": description,
                        "severity": severity,
                        "matches_count": len(matches),
                        "sample": str(matches[0])[:50] if matches else None,
                    }
                )

        return detected


def create_default_detector(strict: bool = False) -> InjectionDetector:
    """
    Cria um detector com configuração padrão

    Args:
        strict: Se True, usa modo estrito

    Returns:
        InjectionDetector configurado
    """
    return InjectionDetector(strict_mode=strict)
