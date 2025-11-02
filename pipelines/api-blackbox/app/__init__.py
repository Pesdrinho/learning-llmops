"""
API Blackbox - Gateway OpenRouter com Governança

Este módulo implementa um gateway inteligente para modelos LLM via OpenRouter,
incluindo funcionalidades essenciais de governança e observabilidade.

Principais funcionalidades:
- Roteamento para múltiplos modelos (gpt-4o-mini, claude-3.5-sonnet, gemini, etc)
- Mascaramento automático de PII (CPF, CNPJ, email, telefone)
- Controle de custos com limite diário (US$15)
- Logging completo de todas as interações
- Métricas de latência e uso

Arquitetura:
    Request → Middleware (PII + Cost) → Router (OpenRouter) → LLM → Response
                  ↓
              Logging (observability.llm_logs)
                  ↓
              Cost Tracking (observability.spend_ledger)
"""

__version__ = "0.1.0"
