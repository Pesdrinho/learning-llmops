"""
Classes Base para Sistema de Prompts

Define estruturas fundamentais para gerenciamento de prompts:
- PromptConfig: Configuração e metadados de prompts
- PromptRegistry: Registro central de prompts versionados
- Utilitários para validação e composição
"""

from datetime import datetime
from typing import Any

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from pydantic import BaseModel, Field, field_validator


class PromptConfig(BaseModel):
    """
    Configuração de um prompt

    Armazena metadados e configurações de guardrails
    para um template de prompt específico.
    """

    version: str = Field(..., description="Versão do prompt (formato semver: 1.0.0)")

    description: str = Field(..., description="Descrição do propósito do prompt")

    variables: list[str] = Field(
        default_factory=list, description="Lista de variáveis esperadas no template"
    )

    guardrails: dict[str, Any] = Field(
        default_factory=dict, description="Configurações de guardrails a serem aplicados"
    )

    created_at: datetime = Field(default_factory=datetime.now, description="Timestamp de criação")

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Valida formato de versão (básico)"""
        parts = v.split(".")
        if len(parts) != 3:
            raise ValueError("Versão deve estar no formato X.Y.Z")
        return v


class PromptRegistry:
    """
    Registro central de prompts

    Mantém controle de todos os prompts disponíveis,
    suas versões e permite versionamento A/B.
    """

    def __init__(self):
        self._prompts: dict[str, dict[str, tuple[Any, PromptConfig]]] = {}

    def register(
        self, name: str, template: ChatPromptTemplate | PromptTemplate, config: PromptConfig
    ) -> None:
        """
        Registra um novo prompt ou versão

        Args:
            name: Nome identificador do prompt
            template: Template LangChain
            config: Configuração do prompt
        """
        if name not in self._prompts:
            self._prompts[name] = {}

        self._prompts[name][config.version] = (template, config)

    def get(self, name: str, version: str | None = None) -> tuple[Any, PromptConfig]:
        """
        Obtém um prompt registrado

        Args:
            name: Nome do prompt
            version: Versão específica (None = versão mais recente)

        Returns:
            Tupla (template, config)

        Raises:
            KeyError: Se prompt não encontrado
        """
        if name not in self._prompts:
            raise KeyError(f"Prompt '{name}' não encontrado")

        versions = self._prompts[name]

        if version:
            if version not in versions:
                raise KeyError(f"Versão '{version}' do prompt '{name}' não encontrada")
            return versions[version]

        latest_version = max(versions.keys())
        return versions[latest_version]

    def list_versions(self, name: str) -> list[str]:
        """Lista todas as versões disponíveis de um prompt"""
        if name not in self._prompts:
            return []
        return list(self._prompts[name].keys())

    def list_prompts(self) -> list[str]:
        """Lista todos os prompts registrados"""
        return list(self._prompts.keys())


registry = PromptRegistry()
