# Evidências Funcionais — Recuperação de Senha (Requisitos 2.1 a 2.7)

Este documento reúne as evidências de que o fluxo de recuperação de
senha do CirculaGov, incluindo o registro em log de cada etapa, está
funcionando corretamente.

## 1. Testes automatizados

O app `recuperacao_senha` conta com 21 testes automatizados, cobrindo
geração e validação de token, expiração, invalidação após uso, mensagem
genérica de falha e o registro em log (requisitos 2.6 e 2.7).

Comando utilizado:

```bash
python manage.py test recuperacao_senha
```

Resultado:

```
Creating test database for alias 'default'...
Found 21 test(s).
----------------------------------------------------------------------
Ran 21 tests in 3.795s

OK
Destroying test database for alias 'default'...
System check identified no issues (0 silenced).
```

Todos os 21 testes passaram, cobrindo:

- Token gerado com CSPRNG, salvo como hash, nunca em texto puro.
- Token expira após 30 minutos e fica inválido após o primeiro uso.
- Resposta idêntica para usuário existente/inexistente e para token
  expirado/usado/inexistente (sem enumeração).
- Toda solicitação de recuperação gera um registro de log, exista ou
  não o usuário (requisito 2.6).
- Sucesso e falha da redefinição são registrados no log com o motivo
  real, sem incluir a senha nova nem o valor do token (requisito 2.7).

## 2. Evidência do arquivo de log em execução real

Além dos testes automatizados, o fluxo foi testado manualmente pelo
navegador: uma solicitação de recuperação para o usuário `admin`,
seguida da redefinição de senha com sucesso, e uma tentativa com um
token inexistente. Conteúdo gerado em `logs/seguranca.log`:

```
2026-09-06 12:17:12,816 INFO seguranca.recuperacao_senha solicitacao de recuperacao de senha para username=admin
2026-09-06 12:17:55,904 INFO seguranca.recuperacao_senha recuperacao de senha concluida com sucesso, username=admin
2026-09-06 12:18:04,464 WARNING seguranca.recuperacao_senha falha na recuperacao de senha, motivo=token_nao_encontrado
```

## 3. Evidências manuais (prints do sistema em execução)

### 3.1 Tela de solicitação de recuperação de senha

[Tela de solicitação](evidencias/05-recuperacao-solicitar.png)

### 3.2 Tela de redefinição de senha (token válido)

[Tela de redefinição](evidencias/06-recuperacao-redefinir.png)

### 3.3 Confirmação de senha redefinida com sucesso

[Senha redefinida](evidencias/07-recuperacao-sucesso.png)

### 3.4 Tela de erro para token inválido/expirado/já usado

[Token inválido](evidencias/08-recuperacao-token-invalido.png)

### 3.5 Mensagem genérica após solicitar recuperação

[Mensagem genérica](evidencias/09-recuperacao-mensagem-generica.png)

Aparece a mesma mensagem, exista ou não o usuário. Reforça a proteção
contra enumeração de contas descrita em `FLUXO_RECUPERACAO_SENHA.md`.
