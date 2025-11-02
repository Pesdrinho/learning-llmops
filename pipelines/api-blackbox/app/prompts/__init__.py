"""
Biblioteca de Prompts - API Blackbox

Este módulo centraliza todos os prompts e templates utilizados na API.
Organizado por categoria para fácil manutenção e versionamento.
"""

from prompts.base import PromptConfig, PromptRegistry
from prompts.chat import get_chat_prompt, get_system_prompt
from prompts.dataset_generation import get_dataset_generation_prompt

__all__ = [
    "PromptConfig",
    "PromptRegistry",
    "get_chat_prompt",
    "get_system_prompt",
    "get_dataset_generation_prompt",
]
