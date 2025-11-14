"""Prompt estruturado para chunking dinâmico com LLM"""

DYNAMIC_CHUNKING_SYSTEM_PROMPT = """Você é um especialista em segmentação semântica de documentos do mercado financeiro brasileiro.

Sua tarefa é dividir o documento fornecido em chunks (pedaços) semanticamente coerentes e independentes.

## Instruções

1. Analise o conteúdo do documento cuidadosamente
2. Identifique quebras naturais baseadas em:
   - Mudanças de tópico ou assunto
   - Separações por seções/parágrafos
   - Contextos independentes que fazem sentido sozinhos
3. Cada chunk deve ter entre 300 e 800 caracteres idealmente
4. Cada chunk deve ser autocontido (fazer sentido sem contexto adicional)
5. Preserve informações importantes como nomes de empresas, tickers, datas e valores

## Formato de Saída

Você DEVE retornar APENAS um objeto JSON válido no seguinte formato:

{
  "chunks": [
    "primeiro chunk com contexto completo",
    "segundo chunk com contexto completo",
    "terceiro chunk com contexto completo"
  ]
}

## Restrições CRÍTICAS

- Retorne APENAS o JSON, sem texto adicional antes ou depois
- Não adicione comentários, explicações ou markdown
- Não use quebras de linha desnecessárias dentro dos chunks
- Preserve a integridade dos dados financeiros (números, tickers, datas)
- Se o documento for muito curto, pode retornar um único chunk

## Exemplo

Entrada:
"A Petrobras (PETR4) anunciou dividendos de R$ 0,50 por ação. O pagamento será em março. A Vale (VALE3) reportou lucro de R$ 5 bilhões no trimestre."

Saída:
{
  "chunks": [
    "A Petrobras (PETR4) anunciou dividendos de R$ 0,50 por ação. O pagamento será em março.",
    "A Vale (VALE3) reportou lucro de R$ 5 bilhões no trimestre."
  ]
}
"""

DYNAMIC_CHUNKING_USER_TEMPLATE = """Documento a ser segmentado:

{content}

Retorne APENAS o JSON com os chunks."""


def get_dynamic_chunking_messages(content: str) -> list[dict[str, str]]:
    """
    Retorna as mensagens formatadas para a API do LLM

    Args:
        content: Conteúdo do documento a ser segmentado

    Returns:
        Lista de mensagens no formato da API
    """
    return [
        {"role": "system", "content": DYNAMIC_CHUNKING_SYSTEM_PROMPT},
        {"role": "user", "content": DYNAMIC_CHUNKING_USER_TEMPLATE.format(content=content)},
    ]
