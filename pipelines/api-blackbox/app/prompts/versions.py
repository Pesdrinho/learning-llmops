"""
Sistema de Versionamento de Prompts

Permite gerenciar múltiplas versões de prompts,
fazer A/B testing e rollback de versões.
"""

from datetime import datetime
from typing import Any

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from prompts.base import PromptConfig, registry

from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


class PromptVersionManager:
    """
    Gerencia versionamento de prompts

    Funcionalidades:
    - Controle de versões semântico (X.Y.Z)
    - A/B testing com distribuição configurável
    - Rollback para versões anteriores
    - Histórico de mudanças
    """

    def __init__(self):
        self.active_versions: dict[str, str] = {}
        self.ab_tests: dict[str, dict[str, float]] = {}
        self.version_history: dict[str, list[dict]] = {}

    def set_active_version(self, prompt_name: str, version: str) -> None:
        """
        Define versão ativa de um prompt

        Args:
            prompt_name: Nome do prompt
            version: Versão a ativar (ex: "1.2.0")
        """
        available_versions = registry.list_versions(prompt_name)

        if version not in available_versions:
            raise ValueError(
                f"Versão {version} não encontrada para prompt {prompt_name}. "
                f"Disponíveis: {available_versions}"
            )

        old_version = self.active_versions.get(prompt_name)
        self.active_versions[prompt_name] = version

        self._record_version_change(prompt_name, old_version, version, "manual_activation")

        logger.info(f"Prompt '{prompt_name}' versão ativada: {old_version} → {version}")

    def get_active_version(self, prompt_name: str) -> str:
        """
        Obtém versão ativa de um prompt

        Args:
            prompt_name: Nome do prompt

        Returns:
            Versão ativa (ou última versão se não configurado)
        """
        if prompt_name in self.active_versions:
            return self.active_versions[prompt_name]

        versions = registry.list_versions(prompt_name)
        if not versions:
            raise ValueError(f"Prompt '{prompt_name}' não encontrado")

        return max(versions)

    def setup_ab_test(self, prompt_name: str, versions_distribution: dict[str, float]) -> None:
        """
        Configura A/B test entre versões

        Args:
            prompt_name: Nome do prompt
            versions_distribution: Dict {version: probability}
                                   Ex: {"1.0.0": 0.5, "1.1.0": 0.5}

        Raises:
            ValueError: Se distribuição não soma 1.0
        """
        total_prob = sum(versions_distribution.values())
        if abs(total_prob - 1.0) > 0.001:
            raise ValueError(f"Distribuição deve somar 1.0 (atual: {total_prob})")

        for version in versions_distribution:
            available = registry.list_versions(prompt_name)
            if version not in available:
                raise ValueError(f"Versão {version} não encontrada. Disponíveis: {available}")

        self.ab_tests[prompt_name] = versions_distribution

        logger.info(f"A/B test configurado para '{prompt_name}': {versions_distribution}")

    def get_version_for_request(self, prompt_name: str, user_id: str | None = None) -> str:
        """
        Obtém versão para uma requisição (considerando A/B test)

        Se houver A/B test ativo, usa hash do user_id para
        garantir consistência (mesmo usuário sempre vê mesma versão).

        Args:
            prompt_name: Nome do prompt
            user_id: ID do usuário (para consistência em A/B)

        Returns:
            Versão a usar
        """
        if prompt_name not in self.ab_tests:
            return self.get_active_version(prompt_name)

        import hashlib

        distribution = self.ab_tests[prompt_name]

        if user_id:
            hash_value = int(hashlib.md5(f"{prompt_name}:{user_id}".encode()).hexdigest()[:8], 16)
            random_value = (hash_value % 10000) / 10000.0
        else:
            import random

            random_value = random.random()

        cumulative_prob = 0.0
        for version, prob in sorted(distribution.items()):
            cumulative_prob += prob
            if random_value <= cumulative_prob:
                return version

        return list(distribution.keys())[-1]

    def remove_ab_test(self, prompt_name: str) -> None:
        """Remove configuração de A/B test"""
        if prompt_name in self.ab_tests:
            del self.ab_tests[prompt_name]
            logger.info(f"A/B test removido para '{prompt_name}'")

    def rollback_to_version(self, prompt_name: str, version: str) -> None:
        """
        Faz rollback para uma versão específica

        Args:
            prompt_name: Nome do prompt
            version: Versão para rollback
        """
        self.set_active_version(prompt_name, version)

        self._record_version_change(
            prompt_name, self.active_versions.get(prompt_name), version, "rollback"
        )

        logger.warning(f"ROLLBACK: Prompt '{prompt_name}' revertido para versão {version}")

    def get_version_history(self, prompt_name: str, limit: int = 10) -> list[dict]:
        """
        Obtém histórico de mudanças de versão

        Args:
            prompt_name: Nome do prompt
            limit: Número máximo de entradas

        Returns:
            Lista de mudanças (mais recente primeiro)
        """
        if prompt_name not in self.version_history:
            return []

        return self.version_history[prompt_name][-limit:][::-1]

    def _record_version_change(
        self, prompt_name: str, old_version: str | None, new_version: str, reason: str
    ) -> None:
        """Registra mudança de versão no histórico"""
        if prompt_name not in self.version_history:
            self.version_history[prompt_name] = []

        self.version_history[prompt_name].append(
            {
                "timestamp": datetime.now(),
                "old_version": old_version,
                "new_version": new_version,
                "reason": reason,
            }
        )

    def get_prompt_with_version(
        self, prompt_name: str, user_id: str | None = None, force_version: str | None = None
    ) -> tuple[ChatPromptTemplate | PromptTemplate, PromptConfig, str]:
        """
        Obtém prompt com versão apropriada

        Args:
            prompt_name: Nome do prompt
            user_id: ID do usuário (para A/B test)
            force_version: Força versão específica

        Returns:
            Tupla (template, config, version_used)
        """
        if force_version:
            version = force_version
        else:
            version = self.get_version_for_request(prompt_name, user_id)

        template, config = registry.get(prompt_name, version)

        return template, config, version

    def compare_versions(self, prompt_name: str, version_a: str, version_b: str) -> dict[str, Any]:
        """
        Compara duas versões de um prompt

        Args:
            prompt_name: Nome do prompt
            version_a: Primeira versão
            version_b: Segunda versão

        Returns:
            Dicionário com comparação
        """
        _, config_a = registry.get(prompt_name, version_a)
        _, config_b = registry.get(prompt_name, version_b)

        return {
            "prompt_name": prompt_name,
            "version_a": version_a,
            "version_b": version_b,
            "created_at_a": config_a.created_at,
            "created_at_b": config_b.created_at,
            "description_a": config_a.description,
            "description_b": config_b.description,
            "variables_a": config_a.variables,
            "variables_b": config_b.variables,
            "guardrails_a": config_a.guardrails,
            "guardrails_b": config_b.guardrails,
        }


version_manager = PromptVersionManager()


def get_prompt_for_inference(
    prompt_name: str, user_id: str | None = None, force_version: str | None = None
) -> tuple[ChatPromptTemplate | PromptTemplate, PromptConfig, str]:
    """
    Helper para obter prompt durante inferência

    Args:
        prompt_name: Nome do prompt
        user_id: ID do usuário
        force_version: Força versão específica

    Returns:
        Tupla (template, config, version)
    """
    return version_manager.get_prompt_with_version(prompt_name, user_id, force_version)
