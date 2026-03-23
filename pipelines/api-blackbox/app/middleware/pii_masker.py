"""
Middleware de Mascaramento de PII (Personally Identifiable Information)

PII = Informações Pessoalmente Identificáveis

Por que mascarar PII?
1. **LGPD/GDPR Compliance**: Proteção de dados pessoais é lei
2. **Segurança**: Evita vazamento em logs
3. **Privacidade**: Modelos LLM não precisam ver dados sensíveis
4. **Auditoria**: Logs podem ser revisados sem expor dados

O que mascaramos?
- CPF: 123.456.789-00 → ***.***.***-**
- CNPJ: 12.345.678/0001-00 → **.***.***/****-**
- Email: usuario@example.com → ***@***.***
- Telefone: (11) 98765-4321 → (11) *****-****

Como funciona?
    Texto original → Regex match → Substituição → Texto mascarado

Exemplo:
    "Meu CPF é 123.456.789-00"
    ↓
    "Meu CPF é ***.***.***-**"
"""

import re
from re import Pattern


class PIIMasker:
    """
    Classe responsável por mascarar informações sensíveis em textos

    Atributos:
        patterns: Dicionário de regex patterns para cada tipo de PII

    Uso:
        masker = PIIMasker()
        texto_seguro = masker.mask("Meu CPF é 123.456.789-00")
        # texto_seguro = "Meu CPF é ***.***.***-**"
    """

    def __init__(self):
        """
        Inicializa os padrões regex para detecção de PII

        Regex (Regular Expressions) = Padrões para busca em texto
        Cada padrão é otimizado para detectar um tipo específico de dado.
        """

        # ========== CPF ==========
        # Formato: 123.456.789-00 ou 12345678900
        # Regex breakdown:
        #   \d{3}       = 3 dígitos
        #   \.?         = ponto opcional
        #   \d{3}       = 3 dígitos
        #   \.?         = ponto opcional
        #   \d{3}       = 3 dígitos
        #   -?          = hífen opcional
        #   \d{2}       = 2 dígitos verificadores
        self.cpf_pattern: Pattern = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")

        # ========== CNPJ ==========
        # Formato: 12.345.678/0001-00 ou 12345678000100
        # Regex breakdown:
        #   \d{2}       = 2 dígitos iniciais
        #   \.?         = ponto opcional
        #   \d{3}       = 3 dígitos
        #   \.?         = ponto opcional
        #   \d{3}       = 3 dígitos
        #   /?          = barra opcional
        #   \d{4}       = 4 dígitos (filial)
        #   -?          = hífen opcional
        #   \d{2}       = 2 dígitos verificadores
        self.cnpj_pattern: Pattern = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\.?\d{4}-?\d{2}\b")

        # ========== EMAIL ==========
        # Formato: usuario@dominio.com
        # Regex breakdown:
        #   [a-zA-Z0-9._%+-]+  = caracteres válidos no usuário
        #   @                  = arroba obrigatória
        #   [a-zA-Z0-9.-]+     = domínio
        #   \.                 = ponto antes da extensão
        #   [a-zA-Z]{2,}       = extensão (mín. 2 caracteres)
        self.email_pattern: Pattern = re.compile(
            r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", re.IGNORECASE
        )

        # ========== TELEFONE ==========
        # Formatos aceitos:
        # - (11) 98765-4321
        # - 11 98765-4321
        # - 11987654321
        # - +55 11 98765-4321
        #
        # Regex breakdown:
        #   (\+55\s?)?         = +55 opcional (país)
        #   \(?                = parêntese opcional
        #   \d{2}              = DDD (2 dígitos)
        #   \)?                = parêntese opcional
        #   \s?                = espaço opcional
        #   \d{4,5}            = 4 ou 5 dígitos (fixo ou celular)
        #   -?                 = hífen opcional
        #   \d{4}              = 4 dígitos finais
        self.phone_pattern: Pattern = re.compile(r"(\+55\s?)?\(?\d{2}\)?\s?\d{4,5}-?\d{4}\b")

        # Compilação de todos os patterns para fácil acesso
        self.patterns = {
            "cpf": self.cpf_pattern,
            "cnpj": self.cnpj_pattern,
            "email": self.email_pattern,
            "phone": self.phone_pattern,
        }

    def mask_cpf(self, text: str) -> str:
        """
        Mascara CPFs no texto

        Estratégia: Substituir apenas os dígitos, preservando pontuação
        para manter a estrutura visual reconhecível.

        Args:
            text: Texto contendo possíveis CPFs

        Returns:
            Texto com CPFs mascarados

        Exemplo:
            >>> masker = PIIMasker()
            >>> masker.mask_cpf("CPF: 123.456.789-00")
            "CPF: ***.***.***-**"
        """

        def replacer(match):
            cpf = match.group(0)
            # Preserva pontuação, mascara dígitos
            masked = re.sub(r"\d", "*", cpf)
            return masked

        return self.cpf_pattern.sub(replacer, text)

    def mask_cnpj(self, text: str) -> str:
        """
        Mascara CNPJs no texto

        Similar ao CPF, mas com estrutura diferente.

        Args:
            text: Texto contendo possíveis CNPJs

        Returns:
            Texto com CNPJs mascarados

        Exemplo:
            >>> masker = PIIMasker()
            >>> masker.mask_cnpj("CNPJ: 12.345.678/0001-00")
            "CNPJ: **.***.***/****-**"
        """

        def replacer(match):
            cnpj = match.group(0)
            masked = re.sub(r"\d", "*", cnpj)
            return masked

        return self.cnpj_pattern.sub(replacer, text)

    def mask_email(self, text: str) -> str:
        """
        Mascara emails no texto

        Estratégia: Preservar apenas estrutura básica (@, .)
        para manter contexto sem expor o email real.

        Args:
            text: Texto contendo possíveis emails

        Returns:
            Texto com emails mascarados

        Exemplo:
            >>> masker = PIIMasker()
            >>> masker.mask_email("Email: user@example.com")
            "Email: ***@***.***"
        """

        def replacer(match):
            email = match.group(0)
            # Divide em usuário e domínio
            if "@" in email:
                user, domain = email.split("@", 1)
                # Mascara usuário completamente
                masked_user = "*" * min(len(user), 3)
                # Mascara domínio, preservando extensão
                if "." in domain:
                    domain_parts = domain.split(".")
                    masked_domain = ".".join(["***"] * len(domain_parts))
                else:
                    masked_domain = "***"
                return f"{masked_user}@{masked_domain}"
            return "***"

        return self.email_pattern.sub(replacer, text)

    def mask_phone(self, text: str) -> str:
        """
        Mascara telefones no texto

        Estratégia: Preservar DDD e formato, mascarar apenas número.

        Args:
            text: Texto contendo possíveis telefones

        Returns:
            Texto com telefones mascarados

        Exemplo:
            >>> masker = PIIMasker()
            >>> masker.mask_phone("Tel: (11) 98765-4321")
            "Tel: (11) *****-****"
        """

        def replacer(match):
            phone = match.group(0)
            # Preserva código do país e DDD, mascara resto
            # (11) 98765-4321 → (11) *****-****
            masked = re.sub(
                r"(\+55\s?)?(\(?\d{2}\)?\s?)(\d{4,5}-?\d{4})",
                lambda m: (m.group(1) or "") + (m.group(2) or "") + re.sub(r"\d", "*", m.group(3)),
                phone,
            )
            return masked

        return self.phone_pattern.sub(replacer, text)

    def mask(self, text: str) -> str:
        """
        Mascara TODOS os tipos de PII no texto

        Aplica todas as máscaras em sequência.
        Ordem importa: CPF antes de telefone (evita falsos positivos).

        Args:
            text: Texto original

        Returns:
            Texto com todas as PII mascaradas

        Exemplo:
            >>> masker = PIIMasker()
            >>> texto = "Dados: CPF 123.456.789-00, email@test.com, (11) 98765-4321"
            >>> masker.mask(texto)
            "Dados: CPF ***.***.***-**, ***@***.*** (11) *****-****"
        """
        if not text:
            return text

        # Aplica máscaras em ordem
        masked_text = text
        masked_text = self.mask_cpf(masked_text)
        masked_text = self.mask_cnpj(masked_text)
        masked_text = self.mask_email(masked_text)
        masked_text = self.mask_phone(masked_text)

        return masked_text

    def has_pii(self, text: str) -> bool:
        """
        Verifica se o texto contém algum tipo de PII

        Útil para logging condicional ou alertas.

        Args:
            text: Texto a verificar

        Returns:
            True se contém PII, False caso contrário

        Exemplo:
            >>> masker = PIIMasker()
            >>> masker.has_pii("Texto normal")
            False
            >>> masker.has_pii("Meu CPF: 123.456.789-00")
            True
        """
        if not text:
            return False

        for pattern in self.patterns.values():
            if pattern.search(text):
                return True

        return False

    def detect_pii_types(self, text: str) -> list[str]:
        """
        Detecta quais tipos de PII estão presentes no texto

        Útil para métricas e auditoria.

        Args:
            text: Texto a analisar

        Returns:
            Lista de tipos de PII detectados

        Exemplo:
            >>> masker = PIIMasker()
            >>> masker.detect_pii_types("CPF: 123.456.789-00, Tel: (11) 98765-4321")
            ['cpf', 'phone']
        """
        if not text:
            return []

        detected = []
        for pii_type, pattern in self.patterns.items():
            if pattern.search(text):
                detected.append(pii_type)

        return detected


# ========== SINGLETON INSTANCE ==========
# Cria uma instância única do masker para reuso
# Singleton pattern = uma única instância compartilhada
# Vantagens:
# - Performance: Regex patterns compilados uma vez só
# - Memória: Não duplica objetos
# - Simplicidade: Import direto do masker

masker = PIIMasker()


# ========== FUNÇÕES DE CONVENIÊNCIA ==========


def mask_text(text: str) -> str:
    """
    Função helper para mascarar texto rapidamente

    Uso direto sem instanciar a classe.

    Args:
        text: Texto a mascarar

    Returns:
        Texto mascarado

    Exemplo:
        >>> from middleware.pii_masker import mask_text
        >>> mask_text("Meu CPF: 123.456.789-00")
        "Meu CPF: ***.***.***-**"
    """
    return masker.mask(text)


def has_pii(text: str) -> bool:
    """
    Função helper para verificar presença de PII

    Args:
        text: Texto a verificar

    Returns:
        True se contém PII

    Exemplo:
        >>> from middleware.pii_masker import has_pii
        >>> has_pii("Texto normal")
        False
    """
    return masker.has_pii(text)
