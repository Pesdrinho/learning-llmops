# Biblioteca de Prompts - API Blackbox

Sistema completo de gerenciamento de prompts com guardrails, versionamento e cache.

## 📚 Visão Geral

A biblioteca de prompts oferece:

- ✅ **Prompts Organizados**: Templates estruturados por categoria
- 🛡️ **Guardrails**: Validação de tópicos, detecção de injection e validação de output
- 📌 **Versionamento**: Controle de versões com A/B testing
- ⚡ **Cache**: Sistema de cache para reduzir custos
- 🎯 **Duas Rotas Especializadas**: Chat completion e dataset generation

## 🚀 Endpoints

### 1. Chat Completion com Guardrails

**Endpoint**: `POST /chat/completion`

```bash
curl -X POST http://localhost:8000/chat/completion \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "messages": [
      {"role": "user", "content": "Explique o que são ações"}
    ],
    "model": "openai/gpt-4o-mini",
    "enable_guardrails": true,
    "conversation_type": "chat_conversation",
    "enable_cache": false
  }'
```

**Parâmetros**:
- `enable_guardrails` (bool): Ativa validações de segurança
- `allowed_topics` (list): Lista de tópicos permitidos (opcional)
- `conversation_type` (str): Tipo de conversa (`chat_conversation`, `financial_advisor`)
- `enable_cache` (bool): Ativa cache de respostas

### 2. Geração de Dataset para Fine-tuning

**Endpoint**: `POST /chat/dataset-generator`

```bash
curl -X POST http://localhost:8000/chat/dataset-generator \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "tool_name": "get_stock_price",
    "tool_description": "Obtém o preço atual de uma ação brasileira na B3",
    "tool_schema": {
      "name": "get_stock_price",
      "description": "Busca preço de ação",
      "parameters": {
        "ticker": "string (ex: PETR4)"
      }
    },
    "num_examples": 20,
    "diversity_level": 0.7,
    "output_format": "jsonl",
    "model": "anthropic/claude-3.5-sonnet"
  }'
```

**Parâmetros**:
- `tool_name` (str): Nome da ferramenta
- `tool_description` (str): Descrição detalhada
- `tool_schema` (dict): Schema JSON da tool
- `num_examples` (int): Quantidade de exemplos (1-100)
- `diversity_level` (float): Nível de variação (0.0-1.0)
- `output_format` (str): `jsonl` ou `array`

## 🛡️ Sistema de Guardrails

### Validações Disponíveis

1. **Topic Validator**: Valida se o conteúdo está dentro dos tópicos permitidos
2. **Injection Detector**: Detecta tentativas de prompt injection
3. **Output Validator**: Valida estrutura e formato das respostas

### Exemplo de Violação

```json
{
  "error": "guardrail_violation",
  "message": "Tópico proibido detectado: hack",
  "violations": [
    {
      "guard": "topic_validator",
      "reason": "Tópico proibido detectado: hack",
      "score": 0.0,
      "type": "input"
    }
  ],
  "request_id": "uuid-here"
}
```

## 📌 Versionamento de Prompts

### Estrutura

Prompts são versionados usando semver (X.Y.Z):

```python
from prompts.versions import version_manager

# Define versão ativa
version_manager.set_active_version("chat_conversation", "1.0.0")

# Configura A/B test
version_manager.setup_ab_test("chat_conversation", {
    "1.0.0": 0.5,  # 50% dos usuários
    "1.1.0": 0.5   # 50% dos usuários
})

# Obtém versão para usuário
version = version_manager.get_version_for_request(
    "chat_conversation",
    user_id="user123"
)
```

### Categorias de Prompts

- **chat_conversation**: Chat geral com guardrails financeiros
- **financial_advisor**: Análise financeira educativa
- **chat_single_turn**: Perguntas simples sem histórico
- **dataset_generation**: Geração de datasets de treinamento

## ⚡ Sistema de Cache

### Configuração

```python
from prompts.templates import get_cached_response, cache_response

# Tenta buscar do cache
cached = await get_cached_response(
    messages=messages,
    model="gpt-4o-mini",
    temperature=0.7,
    ttl_seconds=3600  # 1 hora
)

if cached:
    return cached

# ... gera resposta ...

# Armazena no cache
await cache_response(
    messages=messages,
    model="gpt-4o-mini",
    temperature=0.7,
    response=response_data,
    ttl_seconds=3600
)
```

### Estatísticas

```python
from prompts.templates import get_cache_stats

stats = get_cache_stats()
print(stats)
# {
#   "total_items": 150,
#   "valid_items": 120,
#   "expired_items": 30,
#   "ttl_seconds": 3600
# }
```

## 💰 Rate Limiting Diferenciado

Configure limites específicos por tipo de inferência:

```python
from middleware.cost_limiter import CostLimiter

limiter = CostLimiter(
    daily_limit_usd=20.0,           # Limite geral
    chat_limit_usd=10.0,            # Limite para chat
    dataset_limit_usd=15.0          # Limite para dataset
)

# Verifica limite por tipo
can_process, spent, msg = await limiter.check_limit(
    api_key="key",
    db=db,
    inference_type="chat_completion"
)
```

## 📊 Observabilidade

### Campos no Banco de Dados

A tabela `observability.llm_logs` agora inclui:

- `inference_type`: Tipo de inferência (`chat_completion`, `dataset_generation`)
- `guardrails_triggered`: Lista de guardrails acionados
- `prompt_version`: Versão do prompt utilizado

### Consultas Úteis

```sql
-- Logs por tipo de inferência
SELECT inference_type, COUNT(*), AVG(cost_usd)
FROM observability.llm_logs
GROUP BY inference_type;

-- Guardrails mais acionados
SELECT
    UNNEST(guardrails_triggered) as guardrail,
    COUNT(*) as times_triggered
FROM observability.llm_logs
WHERE guardrails_triggered IS NOT NULL
GROUP BY guardrail
ORDER BY times_triggered DESC;

-- Versões de prompts utilizadas
SELECT prompt_version, COUNT(*), AVG(latency_ms)
FROM observability.llm_logs
GROUP BY prompt_version;
```

## 🔧 Estrutura de Arquivos

```
pipelines/api-blackbox/app/
├── prompts/              # Biblioteca de prompts
│   ├── __init__.py
│   ├── base.py          # Classes base e registry
│   ├── chat.py          # Prompts de chat
│   ├── dataset_generation.py  # Prompts para datasets
│   ├── templates.py     # Helpers e cache
│   └── versions.py      # Sistema de versionamento
├── guards/              # Sistema de guardrails
│   ├── __init__.py
│   ├── topic_validator.py
│   ├── injection_detector.py
│   ├── output_validator.py
│   └── guardrail_chain.py
└── routes/              # Endpoints especializados
    ├── __init__.py
    ├── chat_completion.py
    └── dataset_generator.py
```

## 🎯 Exemplos de Uso

### Exemplo 1: Chat com Tópicos Específicos

```python
request = ChatCompletionRequest(
    messages=[
        ChatMessage(role="user", content="Me fale sobre PETR4")
    ],
    model="openai/gpt-4o-mini",
    enable_guardrails=True,
    allowed_topics=["ações", "bolsa", "petrobras"],
    conversation_type="financial_advisor"
)
```

### Exemplo 2: Geração de Dataset para Tool de Cotações

```python
request = DatasetGenerationRequest(
    tool_name="get_stock_quote",
    tool_description="Busca cotação em tempo real de ações da B3",
    tool_schema={
        "name": "get_stock_quote",
        "description": "Obtém cotação de ação",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "include_fundamentals": {"type": "boolean"}
            },
            "required": ["ticker"]
        }
    },
    num_examples=50,
    diversity_level=0.8
)
```

## 📝 Notas de Implementação

1. **Compatibilidade**: A rota `/chat` original foi mantida para retrocompatibilidade
2. **Schemas SQL**: Execute `scripts/apply_ddls.py` para aplicar as atualizações no banco
3. **Dependências**: Execute `pip install -r requirements.txt` para instalar LangChain
4. **Cache**: É em memória por padrão, considere Redis para produção distribuída
5. **Guardrails**: Podem ser desabilitados individualmente por requisição

## 🚦 Status dos Componentes

| Componente | Status | Descrição |
|------------|--------|-----------|
| Biblioteca de Prompts | ✅ | Completo com LangChain |
| Guardrails | ✅ | Topic, Injection, Output |
| Chat Completion | ✅ | Com guardrails integrados |
| Dataset Generator | ✅ | Formato Qwen |
| Versionamento | ✅ | Com A/B testing |
| Cache | ✅ | Em memória com TTL |
| Rate Limiting | ✅ | Diferenciado por tipo |
| Observabilidade | ✅ | Campos adicionados no DB |

## 📚 Próximos Passos

- [ ] Implementar cache distribuído com Redis
- [ ] Adicionar mais tipos de guardrails (toxicity, bias)
- [ ] Dashboard para métricas de guardrails
- [ ] Exportar datasets gerados para cloud storage
- [ ] Webhook notifications para violações de guardrails

---

**Desenvolvido para learning-llmops** | v1.0.0
