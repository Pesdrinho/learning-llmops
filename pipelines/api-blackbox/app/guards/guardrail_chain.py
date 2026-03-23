"""
Guardrail Chain - Orquestração de Múltiplos Guardrails

Combina e executa múltiplos guardrails em sequência,
agregando resultados e tomando decisões.
"""

from typing import Any

from guards.injection_detector import InjectionDetector
from guards.output_validator import OutputValidator
from guards.topic_validator import TopicValidator

from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


class GuardrailChain:
    """
    Orquestra múltiplos guardrails

    Permite executar validações em sequência e agregar resultados.
    Pode ser configurado para falhar no primeiro erro ou coletar todos.
    """

    def __init__(self, fail_fast: bool = True, log_all_violations: bool = True):
        """
        Inicializa a chain de guardrails

        Args:
            fail_fast: Se True, para na primeira falha
            log_all_violations: Se True, registra todas as violações
        """
        self.fail_fast = fail_fast
        self.log_all_violations = log_all_violations
        self.input_guards: list[tuple[Any, str]] = []
        self.output_guards: list[tuple[Any, str]] = []

    def add_input_guard(
        self, guard: TopicValidator | InjectionDetector, name: str
    ) -> "GuardrailChain":
        """
        Adiciona um guardrail de input

        Args:
            guard: Instância do guardrail
            name: Nome identificador

        Returns:
            Self (para encadeamento)
        """
        self.input_guards.append((guard, name))
        return self

    def add_output_guard(self, guard: OutputValidator, name: str) -> "GuardrailChain":
        """
        Adiciona um guardrail de output

        Args:
            guard: Instância do guardrail
            name: Nome identificador

        Returns:
            Self (para encadeamento)
        """
        self.output_guards.append((guard, name))
        return self

    def validate_input(
        self, text: str, metadata: dict[str, Any] | None = None
    ) -> tuple[bool, list[dict]]:
        """
        Executa validação de input através de todos os guardrails

        Args:
            text: Texto a validar
            metadata: Metadados opcionais

        Returns:
            Tupla (is_valid, violations)
            violations: Lista de dicts com informações das violações
        """
        violations = []

        for guard, name in self.input_guards:
            result = guard.validate(text, metadata)

            if not result.is_valid:
                violation = {
                    "guard": name,
                    "reason": result.reason,
                    "score": result.score,
                    "type": "input",
                }
                violations.append(violation)

                if self.log_all_violations:
                    logger.warning(
                        f"Guardrail '{name}' violado: {result.reason} (score: {result.score})"
                    )

                if self.fail_fast:
                    return False, violations

        is_valid = len(violations) == 0
        return is_valid, violations

    def validate_output(
        self, output: str, metadata: dict[str, Any] | None = None
    ) -> tuple[bool, list[dict]]:
        """
        Executa validação de output através de todos os guardrails

        Args:
            output: Output a validar
            metadata: Metadados opcionais

        Returns:
            Tupla (is_valid, violations)
        """
        violations = []

        for guard, name in self.output_guards:
            result = guard.validate(output, metadata)

            if not result.is_valid:
                violation = {
                    "guard": name,
                    "reason": result.reason,
                    "score": result.score,
                    "type": "output",
                }
                violations.append(violation)

                if self.log_all_violations:
                    logger.warning(
                        f"Guardrail de output '{name}' violado: {result.reason} "
                        f"(score: {result.score})"
                    )

                if self.fail_fast:
                    return False, violations

        is_valid = len(violations) == 0
        return is_valid, violations

    def validate_full_flow(
        self, input_text: str, output_text: str, metadata: dict[str, Any] | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        Valida input E output em um único fluxo

        Args:
            input_text: Texto de input
            output_text: Texto de output
            metadata: Metadados opcionais

        Returns:
            Tupla (is_valid, report)
            report: Dicionário com resultados detalhados
        """
        input_valid, input_violations = self.validate_input(input_text, metadata)
        output_valid, output_violations = self.validate_output(output_text, metadata)

        is_valid = input_valid and output_valid

        report = {
            "is_valid": is_valid,
            "input_violations": input_violations,
            "output_violations": output_violations,
            "total_violations": len(input_violations) + len(output_violations),
            "guardrails_executed": {
                "input": len(self.input_guards),
                "output": len(self.output_guards),
                "total": len(self.input_guards) + len(self.output_guards),
            },
        }

        return is_valid, report

    def get_triggered_guards(self, violations: list[dict]) -> dict[str, list[str]]:
        """
        Extrai nomes dos guardrails que foram violados

        Args:
            violations: Lista de violações

        Returns:
            Dict com guardrails por tipo
        """
        triggered = {"input": [], "output": []}

        for violation in violations:
            guard_type = violation.get("type", "unknown")
            guard_name = violation.get("guard", "unknown")

            if guard_type in triggered and guard_name not in triggered[guard_type]:
                triggered[guard_type].append(guard_name)

        return triggered


def create_default_chain(
    enable_topic_validation: bool = True,
    enable_injection_detection: bool = True,
    enable_output_validation: bool = True,
    allowed_topics: list[str] | None = None,
) -> GuardrailChain:
    """
    Cria uma chain com guardrails padrão

    Args:
        enable_topic_validation: Habilitar validação de tópicos
        enable_injection_detection: Habilitar detecção de injection
        enable_output_validation: Habilitar validação de output
        allowed_topics: Lista de tópicos permitidos

    Returns:
        GuardrailChain configurada
    """
    chain = GuardrailChain(fail_fast=True, log_all_violations=True)

    if enable_topic_validation:
        topic_validator = TopicValidator(allowed_topics=allowed_topics)
        chain.add_input_guard(topic_validator, "topic_validator")

    if enable_injection_detection:
        injection_detector = InjectionDetector(strict_mode=False)
        chain.add_input_guard(injection_detector, "injection_detector")

    if enable_output_validation:
        output_validator = OutputValidator(expected_format="text")
        chain.add_output_guard(output_validator, "output_validator")

    return chain


def create_financial_chain(strict: bool = False) -> GuardrailChain:
    """
    Cria uma chain específica para domínio financeiro

    Args:
        strict: Se True, usa validação mais rigorosa

    Returns:
        GuardrailChain configurada para finanças
    """
    from guards.topic_validator import create_financial_topic_validator

    chain = GuardrailChain(fail_fast=True, log_all_violations=True)

    topic_validator = create_financial_topic_validator()
    chain.add_input_guard(topic_validator, "financial_topic_validator")

    injection_detector = InjectionDetector(strict_mode=strict)
    chain.add_input_guard(injection_detector, "injection_detector")

    output_validator = OutputValidator(expected_format="text", max_length=4000)
    chain.add_output_guard(output_validator, "output_validator")

    return chain


def create_dataset_generation_chain() -> GuardrailChain:
    """
    Cria uma chain para validar geração de datasets

    Returns:
        GuardrailChain configurada para datasets
    """
    from guards.output_validator import create_dataset_validator

    chain = GuardrailChain(fail_fast=False, log_all_violations=True)

    injection_detector = InjectionDetector(strict_mode=False)
    chain.add_input_guard(injection_detector, "injection_detector")

    dataset_validator = create_dataset_validator()
    chain.add_output_guard(dataset_validator, "dataset_validator")

    return chain
