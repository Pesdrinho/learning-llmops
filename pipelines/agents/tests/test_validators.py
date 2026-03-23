"""
Testes para Validadores

Testa validação de SQL e análises.
"""

from app.tools.validators import (
    check_sql_blacklist,
    check_sql_syntax,
    check_sql_whitelist,
    validate_analysis_output,
    validate_sql_query,
)


class TestSQLValidation:
    """Testes de validação SQL"""

    def test_valid_query(self):
        """Testa query válida"""
        query = "SELECT ticker, date, close FROM market.ohlcv WHERE ticker = 'PETR4'"
        is_valid, error = validate_sql_query(query)
        assert is_valid
        assert error == ""

    def test_blacklisted_command(self):
        """Testa comando na blacklist"""
        query = "DROP TABLE market.ohlcv"
        is_valid, error = check_sql_blacklist(query)
        assert not is_valid
        assert "DROP" in error

    def test_non_whitelisted_table(self):
        """Testa acesso a tabela não permitida"""
        query = "SELECT * FROM users"
        is_valid, error = check_sql_whitelist(query)
        assert not is_valid
        assert "permitida" in error.lower()

    def test_syntax_error(self):
        """Testa erro de sintaxe"""
        query = "SELECT FROM WHERE"
        is_valid, error = check_sql_syntax(query)
        assert not is_valid

    def test_delete_command(self):
        """Testa comando DELETE"""
        query = "DELETE FROM market.ohlcv WHERE ticker = 'PETR4'"
        is_valid, error = check_sql_blacklist(query)
        assert not is_valid
        assert "DELETE" in error

    def test_update_command(self):
        """Testa comando UPDATE"""
        query = "UPDATE market.ohlcv SET close = 0"
        is_valid, error = check_sql_blacklist(query)
        assert not is_valid
        assert "UPDATE" in error


class TestAnalysisValidation:
    """Testes de validação de análises"""

    def test_valid_analysis(self):
        """Testa análise válida"""
        content = "# Análise de PETR4\n\n" + "Conteúdo da análise " * 50
        is_valid, error = validate_analysis_output(content)
        assert is_valid
        assert error == ""

    def test_too_short_analysis(self):
        """Testa análise muito curta"""
        content = "# Análise"
        is_valid, error = validate_analysis_output(content)
        assert not is_valid
        assert "curta" in error.lower()

    def test_no_header_analysis(self):
        """Testa análise sem cabeçalho"""
        content = "Análise sem cabeçalho markdown " * 20
        is_valid, error = validate_analysis_output(content)
        assert not is_valid
        assert "cabeçalho" in error.lower()

    def test_too_long_analysis(self):
        """Testa análise muito longa"""
        content = "# Análise\n\n" + "Conteúdo " * 10000
        is_valid, error = validate_analysis_output(content)
        assert not is_valid
        assert "longa" in error.lower()
