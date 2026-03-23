"""
Prompts para Geração de Datasets

Templates especializados para gerar dados de treinamento
no formato Qwen para fine-tuning com tool calling.
"""

from langchain_core.prompts import ChatPromptTemplate
from prompts.base import PromptConfig, registry

DATASET_GENERATION_SYSTEM_PROMPT = """Você é um gerador especializado de exemplos de treinamento para modelos de linguagem com capacidade de tool calling.

Sua tarefa é criar exemplos DIVERSOS e REALISTAS de interações onde um usuário faz uma pergunta e o assistente decide chamar uma ferramenta (tool) específica.

## Requisitos para os Exemplos

1. **Diversidade**: Varie o estilo, complexidade e contexto das perguntas
2. **Realismo**: Crie perguntas que usuários reais fariam
3. **Cobertura**: Cubra diferentes cenários de uso da tool
4. **Clareza**: Os parâmetros extraídos devem ser claros e corretos

## Formato de Output

Você DEVE retornar um JSON válido com a seguinte estrutura:

```json
{{
  "messages": [
    {{
      "role": "system",
      "content": "You are a helpful assistant with access to tools."
    }},
    {{
      "role": "user",
      "content": "<pergunta_do_usuario>"
    }},
    {{
      "role": "assistant",
      "content": "",
      "tool_calls": [
        {{
          "name": "<nome_da_tool>",
          "arguments": {{
            "<param1>": "<valor1>",
            "<param2>": "<valor2>"
          }}
        }}
      ]
    }}
  ]
}}
```

## Instruções Importantes

- O campo "content" do assistant deve estar VAZIO quando há tool_calls
- Os argumentos devem corresponder EXATAMENTE ao schema da tool
- Extraia parâmetros do contexto da pergunta do usuário
- Se múltiplas tools forem necessárias, inclua múltiplas tool_calls
"""


DATASET_GENERATION_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system", DATASET_GENERATION_SYSTEM_PROMPT),
        (
            "user",
            """Gere {num_examples} exemplos de treinamento para a seguinte tool:

## Tool Description
Nome: {tool_name}
Descrição: {tool_description}

## Tool Schema
{tool_schema}

## Nível de Diversidade
{diversity_level} (0.0 = similar, 1.0 = muito diverso)

Retorne um array JSON com {num_examples} exemplos no formato especificado.
Cada exemplo deve ser DIFERENTE dos outros, variando:
- Tom da pergunta (formal, casual, técnico)
- Complexidade (simples, média, complexa)
- Contexto (diferentes cenários de uso)
- Parâmetros (valores diferentes mas válidos)

OUTPUT (apenas JSON válido, sem explicações):""",
        ),
    ]
)


TOOL_SCHEMA_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Você é um especialista em formatar schemas de tools para fine-tuning de LLMs.

Sua tarefa é pegar uma descrição de tool e gerar um schema JSON válido no formato esperado.""",
        ),
        (
            "user",
            """Formate o seguinte schema de tool:

Nome: {tool_name}
Descrição: {tool_description}
Parâmetros: {parameters}

Retorne APENAS o schema JSON no formato:
{{
  "name": "...",
  "description": "...",
  "parameters": {{
    "type": "object",
    "properties": {{...}},
    "required": [...]
  }}
}}""",
        ),
    ]
)


dataset_generation_config = PromptConfig(
    version="1.0.0",
    description="Prompt para gerar datasets de fine-tuning com tool calling no formato Qwen",
    variables=["num_examples", "tool_name", "tool_description", "tool_schema", "diversity_level"],
    guardrails={
        "enable_output_validation": True,
        "expected_format": "json_array",
        "validate_tool_calls": True,
    },
)

tool_schema_config = PromptConfig(
    version="1.0.0",
    description="Prompt para formatar schemas de tools",
    variables=["tool_name", "tool_description", "parameters"],
    guardrails={
        "enable_output_validation": True,
        "expected_format": "json",
    },
)


registry.register("dataset_generation", DATASET_GENERATION_TEMPLATE, dataset_generation_config)
registry.register("tool_schema_formatter", TOOL_SCHEMA_TEMPLATE, tool_schema_config)


def get_dataset_generation_prompt(
    version: str | None = None,
) -> tuple[ChatPromptTemplate, PromptConfig]:
    """
    Obtém template para geração de datasets

    Args:
        version: Versão específica (None = mais recente)

    Returns:
        Tupla (template, config)
    """
    return registry.get("dataset_generation", version)


def format_tool_schema(tool_dict: dict) -> str:
    """
    Formata um dicionário de tool em string para o prompt

    Args:
        tool_dict: Dicionário com name, description, parameters

    Returns:
        String formatada do schema
    """
    import json

    return json.dumps(tool_dict, indent=2, ensure_ascii=False)


def get_diversity_description(diversity_level: float) -> str:
    """
    Converte nível de diversidade em descrição textual

    Args:
        diversity_level: Float entre 0.0 e 1.0

    Returns:
        Descrição textual do nível
    """
    if diversity_level < 0.3:
        return "0.0 - Exemplos similares com pequenas variações"
    elif diversity_level < 0.6:
        return "0.5 - Equilíbrio entre similaridade e variedade"
    else:
        return "1.0 - Máxima diversidade em estilo, tom e complexidade"
