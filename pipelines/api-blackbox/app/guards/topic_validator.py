"""
Topic Validator - Validação de Tópicos Permitidos/Proibidos

Garante que as requisições estão dentro do escopo esperado,
rejeitando tópicos proibidos ou fora do domínio.
"""

from typing import Any

from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


class ValidationResult:
    """Resultado de uma validação"""

    def __init__(self, is_valid: bool, reason: str | None = None, score: float = 1.0):
        self.is_valid = is_valid
        self.reason = reason
        self.score = score

    def __bool__(self):
        return self.is_valid

    def to_dict(self) -> dict:
        return {"is_valid": self.is_valid, "reason": self.reason, "score": self.score}


class TopicValidator:
    """
    Valida se o conteúdo está dentro dos tópicos permitidos

    Estratégias:
    - Lista de tópicos permitidos (whitelist)
    - Lista de tópicos proibidos (blacklist)
    - Detecção por palavras-chave
    """

    def __init__(
        self,
        allowed_topics: list[str] | None = None,
        forbidden_topics: list[str] | None = None,
        case_sensitive: bool = False,
    ):
        """
        Inicializa o validador de tópicos

        Args:
            allowed_topics: Lista de tópicos permitidos
            forbidden_topics: Lista de tópicos proibidos
            case_sensitive: Se a comparação deve ser case-sensitive
        """
        self.allowed_topics = allowed_topics or []
        self.forbidden_topics = forbidden_topics or self._get_default_forbidden_topics()
        self.case_sensitive = case_sensitive

        if not case_sensitive:
            self.allowed_topics = [t.lower() for t in self.allowed_topics]
            self.forbidden_topics = [t.lower() for t in self.forbidden_topics]

    @staticmethod
    def _get_default_forbidden_topics() -> list[str]:
        """Retorna lista padrão de tópicos proibidos"""
        return [
            "violência",
            "drogas",
            "armas",
            "conteúdo adulto",
            "discriminação",
            "ódio",
            "ilegal",
            "fraude",
            "hack",
            "pirataria",
            "malware",
            "golpe",
            "político",
            "religioso",
        ]

    def validate(self, text: str, metadata: dict[str, Any] | None = None) -> ValidationResult:
        """
        Valida se o texto está dentro dos tópicos permitidos

        Args:
            text: Texto a validar
            metadata: Metadados adicionais (opcional)

        Returns:
            ValidationResult com resultado da validação
        """
        if not text or not text.strip():
            return ValidationResult(False, "Texto vazio")

        content = text if self.case_sensitive else text.lower()

        if self.forbidden_topics:
            for forbidden in self.forbidden_topics:
                if forbidden in content:
                    logger.warning(f"Tópico proibido detectado: {forbidden}")
                    return ValidationResult(False, f"Tópico proibido detectado: {forbidden}", 0.0)

        if self.allowed_topics:
            matched = False
            for allowed in self.allowed_topics:
                if allowed in content:
                    matched = True
                    break

            if not matched:
                logger.warning("Nenhum tópico permitido encontrado")
                return ValidationResult(
                    False,
                    "Conteúdo fora do escopo permitido. Tópicos permitidos: "
                    + ", ".join(self.allowed_topics[:5]),
                    0.0,
                )

        return ValidationResult(True, "Validação aprovada", 1.0)

    def add_allowed_topic(self, topic: str) -> None:
        """Adiciona um tópico à lista de permitidos"""
        topic_normalized = topic if self.case_sensitive else topic.lower()
        if topic_normalized not in self.allowed_topics:
            self.allowed_topics.append(topic_normalized)

    def add_forbidden_topic(self, topic: str) -> None:
        """Adiciona um tópico à lista de proibidos"""
        topic_normalized = topic if self.case_sensitive else topic.lower()
        if topic_normalized not in self.forbidden_topics:
            self.forbidden_topics.append(topic_normalized)

    def remove_allowed_topic(self, topic: str) -> None:
        """Remove um tópico da lista de permitidos"""
        topic_normalized = topic if self.case_sensitive else topic.lower()
        if topic_normalized in self.allowed_topics:
            self.allowed_topics.remove(topic_normalized)

    def remove_forbidden_topic(self, topic: str) -> None:
        """Remove um tópico da lista de proibidos"""
        topic_normalized = topic if self.case_sensitive else topic.lower()
        if topic_normalized in self.forbidden_topics:
            self.forbidden_topics.remove(topic_normalized)

    def get_config(self) -> dict:
        """Retorna configuração atual do validador"""
        return {
            "allowed_topics": self.allowed_topics,
            "forbidden_topics": self.forbidden_topics,
            "case_sensitive": self.case_sensitive,
        }


def create_financial_topic_validator() -> TopicValidator:
    """
    Cria um validador pré-configurado para tópicos financeiros

    Returns:
        TopicValidator configurado para domínio financeiro
    """
    allowed = [
        "ações",
        "bolsa",
        "b3",
        "investimento",
        "fundo",
        "renda fixa",
        "renda variável",
        "tesouro",
        "cdb",
        "lci",
        "lca",
        "debenture",
        "dividendo",
        "cotação",
        "preço",
        "análise",
        "balanço",
        "demonstrativo",
        "lucro",
        "receita",
        "ebitda",
        "p/l",
        "roe",
        "patrimônio",
        "mercado",
        "economia",
        "inflação",
        "selic",
        "juros",
        "ibovespa",
        "ticker",
        "papel",
    ]

    return TopicValidator(allowed_topics=allowed)
