# 🤝 Guia de Contribuição - LLMOps Lab

Obrigado por considerar contribuir para o LLMOps Lab! Este documento fornece diretrizes para tornar o processo de contribuição claro e eficiente.

## 📋 Sumário

- [Código de Conduta](#código-de-conduta)
- [Como Contribuir](#como-contribuir)
- [Configuração do Ambiente](#configuração-do-ambiente)
- [Padrões de Código](#padrões-de-código)
- [Processo de Pull Request](#processo-de-pull-request)
- [Reportando Bugs](#reportando-bugs)
- [Sugerindo Melhorias](#sugerindo-melhorias)

---

## 📜 Código de Conduta

Este projeto adere a um código de conduta. Ao participar, você concorda em manter um ambiente respeitoso e acolhedor para todos.

---

## 🚀 Como Contribuir

### Tipos de Contribuição

- 🐛 **Correção de bugs**
- ✨ **Novas features**
- 📚 **Melhorias na documentação**
- 🧪 **Adição de testes**
- 🎨 **Melhorias de UX/UI**
- ⚡ **Otimizações de performance**

---

## 🛠️ Configuração do Ambiente

### 1. Fork e Clone

```bash
# Fork no GitHub e clone seu fork
git clone https://github.com/SEU-USUARIO/llmops-lab.git
cd llmops-lab

# Adicione o repositório original como upstream
git remote add upstream https://github.com/ORIGINAL-OWNER/llmops-lab.git
```

### 2. Ambiente Virtual

```bash
# Crie e ative o ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

### 3. Instalação de Dependências

```bash
# Instale dependências de desenvolvimento
make dev-install

# Ou manualmente:
pip install -e ".[dev]"
pre-commit install
```

### 4. Banco de Dados Local

```bash
# Suba PostgreSQL local
make db-up

# Aplique DDLs
make db-init
```

### 5. Configure Variáveis de Ambiente

```bash
cp env.example .env
# Edite .env com suas credenciais
```

---

## 📏 Padrões de Código

### Estilo de Código

Este projeto segue as seguintes convenções:

#### Python
- **PEP 8** como base
- **Ruff** para linting e formatação
- **Type hints** sempre que possível
- **Docstrings** no formato Google/NumPy

```python
def exemplo_funcao(param1: str, param2: int) -> dict:
    """
    Descrição breve da função.

    Args:
        param1: Descrição do parâmetro 1
        param2: Descrição do parâmetro 2

    Returns:
        Descrição do retorno
    """
    return {"resultado": "ok"}
```

#### Nomenclatura
- **Classes**: `PascalCase`
- **Funções/Variáveis**: `snake_case`
- **Constantes**: `UPPER_SNAKE_CASE`
- **Privado**: prefixo `_`

### Princípios de Design

1. **Responsabilidade Única**: Cada módulo/função tem uma única responsabilidade
2. **DRY (Don't Repeat Yourself)**: Evite duplicação de código
3. **KISS (Keep It Simple, Stupid)**: Mantenha simples
4. **Código Limpo**: Sem validações desnecessárias, loops aninhados excessivos
5. **Testável**: Código deve ser facilmente testável

### Imports

```python
# Ordem de imports
# 1. Standard library
import os
from typing import Optional

# 2. Third-party
import httpx
from fastapi import FastAPI

# 3. Local
from llmops_lab.config import settings
from llmops_lab.logging import logger
```

---

## 🔄 Processo de Pull Request

### 1. Crie uma Branch

```bash
# Atualize seu main
git checkout main
git pull upstream main

# Crie uma branch descritiva
git checkout -b feat/minha-feature
# ou
git checkout -b fix/correcao-bug
```

### 2. Faça suas Mudanças

```bash
# Desenvolva sua feature/correção
# Execute testes localmente
make test

# Execute linter
make lint

# Execute pre-commit
make pre-commit-run
```

### 3. Commit

Use **Conventional Commits**:

```bash
# Formato: <tipo>(<escopo>): <descrição>

git commit -m "feat(rag): adiciona suporte a reranking"
git commit -m "fix(crawler): corrige bug de duplicação de dados"
git commit -m "docs(readme): atualiza instruções de setup"
git commit -m "test(api): adiciona testes para endpoint /chat"
```

**Tipos de Commit:**
- `feat`: Nova feature
- `fix`: Correção de bug
- `docs`: Documentação
- `test`: Testes
- `refactor`: Refatoração
- `perf`: Melhorias de performance
- `chore`: Tarefas de manutenção

### 4. Push e PR

```bash
# Push para seu fork
git push origin feat/minha-feature
```

Abra um Pull Request no GitHub com:

- **Título claro** seguindo Conventional Commits
- **Descrição detalhada** do que foi feito
- **Issues relacionadas** (ex: "Closes #123")
- **Screenshots** (se aplicável)
- **Checklist** preenchido

#### Template de PR

```markdown
## Descrição
Breve descrição das mudanças

## Tipo de Mudança
- [ ] 🐛 Correção de bug
- [ ] ✨ Nova feature
- [ ] 📚 Documentação
- [ ] 🧪 Testes
- [ ] ♻️ Refatoração

## Checklist
- [ ] Testes adicionados/atualizados
- [ ] Documentação atualizada
- [ ] Linter passou (ruff)
- [ ] Pre-commit passou
- [ ] Testes E2E executados (se aplicável)

## Issues Relacionadas
Closes #123
```

---

## 🐛 Reportando Bugs

### Antes de Reportar

1. Verifique se o bug já foi reportado nas [Issues](https://github.com/OWNER/llmops-lab/issues)
2. Tente reproduzir com a última versão do código
3. Colete informações relevantes

### Template de Bug Report

```markdown
**Descrição do Bug**
Descrição clara e concisa do bug

**Como Reproduzir**
1. Vá para '...'
2. Execute '...'
3. Veja erro

**Comportamento Esperado**
O que deveria acontecer

**Screenshots**
Se aplicável, adicione screenshots

**Ambiente:**
 - OS: [Windows/Linux/Mac]
 - Python: [3.10/3.11]
 - Versão: [0.1.0]

**Logs**
```
Cole logs relevantes aqui
```

**Contexto Adicional**
Qualquer outra informação relevante
```

---

## 💡 Sugerindo Melhorias

### Template de Feature Request

```markdown
**A feature está relacionada a um problema?**
Descrição clara do problema. Ex: "Sempre fico frustrado quando [...]"

**Solução Proposta**
Descrição clara da solução desejada

**Alternativas Consideradas**
Outras soluções que você considerou

**Contexto Adicional**
Screenshots, mockups, diagramas, etc.
```

---

## ✅ Checklist de Revisão de Código

Antes de submeter um PR, certifique-se de que:

- [ ] **Código segue os padrões** do projeto
- [ ] **Testes foram adicionados** para novas funcionalidades
- [ ] **Todos os testes passam** (`make test`)
- [ ] **Linter passa** (`make lint`)
- [ ] **Pre-commit passa** (`make pre-commit-run`)
- [ ] **Documentação foi atualizada** (se necessário)
- [ ] **README atualizado** (se necessário)
- [ ] **Sem console.logs ou prints** desnecessários
- [ ] **Commits seguem Conventional Commits**
- [ ] **Branch está atualizada** com main

---

## 🧪 Testes

### Executando Testes

```bash
# Todos os testes
make test

# Apenas unitários
make test-unit

# Integração
make test-integration

# E2E
make test-e2e

# Com coverage
pytest --cov=llmops_lab --cov-report=html
```

### Escrevendo Testes

```python
# tests/unit/test_exemplo.py
import pytest
from llmops_lab.utils import exemplo_funcao

def test_exemplo_funcao():
    """Testa exemplo_funcao com input válido"""
    resultado = exemplo_funcao("input")
    assert resultado == "esperado"

@pytest.mark.asyncio
async def test_exemplo_async():
    """Testa função assíncrona"""
    resultado = await exemplo_async()
    assert resultado is not None
```

---

## 📁 Estrutura de Arquivos

Ao adicionar novos arquivos, siga a estrutura:

```
pipelines/nova-feature/
├── README.md              # Documentação da feature
├── app/                   # Código principal
│   ├── __init__.py
│   └── main.py
├── tests/                 # Testes
│   ├── test_unit.py
│   └── test_integration.py
├── Dockerfile.dev         # Docker para dev
├── Dockerfile.prod        # Docker para prod
└── cloudbuild.yaml        # Build config (se aplicável)
```

---

## 🔍 Revisão de Código

### O que Revisores Avaliam

1. **Funcionalidade**: O código faz o que deveria?
2. **Legibilidade**: O código é fácil de entender?
3. **Manutenibilidade**: Fácil de modificar no futuro?
4. **Performance**: Há gargalos óbvios?
5. **Segurança**: Há vulnerabilidades?
6. **Testes**: Cobertura adequada?

### Como Responder a Feedback

- ✅ Seja receptivo a sugestões
- ✅ Faça perguntas se algo não estiver claro
- ✅ Marque threads como resolvidas após implementar
- ✅ Agradeça pelo tempo do revisor

---

## 📞 Dúvidas?

- 💬 Abra uma [Discussion](https://github.com/OWNER/llmops-lab/discussions)
- 📧 Entre em contato via issue
- 📖 Consulte a [documentação](docs/)

---

## 🎉 Obrigado!

Sua contribuição é valiosa para tornar o LLMOps Lab melhor para todos!

---

**Happy Coding! 🚀**
