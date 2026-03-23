"""
Validadores para SQL e conteúdo de análises

Fornece validação de queries SQL e validação de conteúdo gerado.
"""

import re

import sqlglot
from sqlglot import parse_one
from sqlglot.errors import ParseError

from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


ALLOWED_TABLES = ["market.ohlcv"]

BLACKLISTED_COMMANDS = [
    "DROP",
    "DELETE",
    "UPDATE",
    "INSERT",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "GRANT",
    "REVOKE",
]


def validate_sql_query(query: str) -> tuple[bool, str]:
    """
    Valida completamente uma query SQL

    Args:
        query: Query SQL a validar

    Returns:
        Tupla (is_valid, error_message)
    """
    query = query.strip()

    if not query:
        return False, "Query vazia"

    valid, error = check_sql_blacklist(query)
    if not valid:
        return False, error

    valid, error = check_sql_syntax(query)
    if not valid:
        return False, error

    valid, error = check_sql_whitelist(query)
    if not valid:
        return False, error

    return True, ""


def check_sql_syntax(query: str) -> tuple[bool, str]:
    """
    Valida sintaxe SQL usando sqlglot

    Args:
        query: Query SQL

    Returns:
        Tupla (is_valid, error_message)
    """
    try:
        parse_one(query, dialect="postgres")
        return True, ""
    except ParseError as e:
        logger.warning(f"SQL syntax error: {e}")
        return False, f"Erro de sintaxe SQL: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error parsing SQL: {e}")
        return False, f"Erro ao validar SQL: {str(e)}"


def check_sql_whitelist(query: str) -> tuple[bool, str]:
    """
    Verifica se query acessa apenas tabelas permitidas

    Args:
        query: Query SQL

    Returns:
        Tupla (is_valid, error_message)
    """
    query_upper = query.upper()

    found_tables = set()

    for table in ALLOWED_TABLES:
        if table.upper() in query_upper:
            found_tables.add(table)

    table_pattern = r"\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*\.?[a-zA-Z_][a-zA-Z0-9_]*)"
    matches = re.findall(table_pattern, query_upper, re.IGNORECASE)

    for match in matches:
        table_normalized = match.strip().lower()
        if table_normalized not in [t.lower() for t in ALLOWED_TABLES]:
            return (
                False,
                f"Acesso negado à tabela '{match}'. Tabelas permitidas: {', '.join(ALLOWED_TABLES)}",
            )

    if not found_tables:
        return (
            False,
            f"Nenhuma tabela permitida encontrada. Tabelas permitidas: {', '.join(ALLOWED_TABLES)}",
        )

    return True, ""


def check_sql_blacklist(query: str) -> tuple[bool, str]:
    """
    Verifica se query contém comandos proibidos

    Args:
        query: Query SQL

    Returns:
        Tupla (is_valid, error_message)
    """
    query_upper = query.upper()

    for cmd in BLACKLISTED_COMMANDS:
        pattern = rf"\b{cmd}\b"
        if re.search(pattern, query_upper):
            return False, f"Comando '{cmd}' não permitido. Apenas queries SELECT são aceitas."

    return True, ""


def validate_analysis_output(content: str) -> tuple[bool, str]:
    """
    Valida se o conteúdo de análise está em formato adequado

    Args:
        content: Conteúdo da análise em markdown

    Returns:
        Tupla (is_valid, error_message)
    """
    if not content or len(content.strip()) < 100:
        return False, "Análise muito curta (mínimo 100 caracteres)"

    if len(content) > 50000:
        return False, "Análise muito longa (máximo 50000 caracteres)"

    has_header = content.strip().startswith("#")
    if not has_header:
        return False, "Análise deve começar com cabeçalho markdown (#)"

    return True, ""


def sanitize_sql_query(query: str) -> str:
    """
    Sanitiza query SQL removendo comandos perigosos

    Args:
        query: Query SQL

    Returns:
        Query sanitizada
    """
    query = query.strip()

    query = re.sub(r"--.*$", "", query, flags=re.MULTILINE)
    query = re.sub(r"/\*.*?\*/", "", query, flags=re.DOTALL)

    query = re.sub(r"\s+", " ", query)

    return query.strip()


def extract_table_names(query: str) -> list[str]:
    """
    Extrai nomes de tabelas de uma query SQL

    Args:
        query: Query SQL

    Returns:
        Lista de nomes de tabelas
    """
    try:
        parsed = parse_one(query, dialect="postgres")
        tables = []

        for table in parsed.find_all(sqlglot.exp.Table):
            table_name = str(table)
            tables.append(table_name)

        return tables
    except Exception as e:
        logger.warning(f"Erro ao extrair tabelas: {e}")
        return []
