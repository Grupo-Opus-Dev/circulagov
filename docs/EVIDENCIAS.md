# Evidências Funcionais — Autenticação (Issue 1.8)

Este documento reúne as evidências de que o fluxo de autenticação
(login, 2FA e logout) do CirculaGov está funcionando corretamente.

## 1. Testes automatizados

O projeto conta com 17 testes automatizados cobrindo login, logout,
expiração de sessão e autenticação em dois fatores (2FA), localizados em
`usuarios/tests.py` e `dois_fatores/tests.py`.

Comando utilizado:

\`\`\`bash
python manage.py test
\`\`\`

Resultado:

\`\`\`
Found 17 test(s).
Creating test database for alias 'default'...
System check identified no issues (0 silenced).
.................

---

Ran 17 tests in 1.742s

OK
Destroying test database for alias 'default'...
\`\`\`

Todos os 17 testes passaram, cobrindo:

- Login exige credenciais corretas.
- Usuário com 2FA ativado não é autenticado apenas com senha.
- Logout remove a sessão do banco de dados e invalida o cookie antigo.
- Sessão expira automaticamente após o tempo máximo configurado.

## 2. Evidências manuais (prints do sistema em execução)

### 2.1 Tela de login

[Tela de login](evidencias/01-tela-login.png)

### 2.2 Testes automatizados passando no terminal

[Testes passando](evidencias/02-testes-passando.png)

### 2.3 Tela inicial após login bem-sucedido

[Tela inicial logado](evidencias/03-tela-inicial-logado.png)

### 2.4 Verificação do código de dois fatores (2FA)

[Verificação 2FA](evidencias/04-verificacao-2fa.png)

O 2FA foi ativado e testado manualmente: após a ativação, o login
passou a exigir o código do aplicativo autenticador antes de conceder
acesso ao sistema, confirmando o comportamento implementado em
`usuarios/views.py` (`LoginComDoisFatoresView`) e
`dois_fatores/views.py`.
