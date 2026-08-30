# Fluxo de Autenticação — CirculaGov (Issue 1.7)

Este documento descreve, passo a passo, como funciona o login no
CirculaGov, incluindo o fluxo de autenticação em dois fatores (2FA).

## Visão geral

O login acontece em até duas etapas:

1. **Senha** — sempre obrigatória.
2. **Código de dois fatores (2FA)** — só acontece se o usuário tiver
   ativado o 2FA na própria conta. Se não tiver ativado, o login
   termina na etapa 1.

## Passo a passo

### 1. Acesso a uma página protegida

Qualquer página que exija login (como a página inicial, que usa o
decorador `@login_required` em `usuarios/views.py`) redireciona
automaticamente o usuário não autenticado para `/contas/login/`.

### 2. Envio de usuário e senha

O usuário preenche o formulário em `templates/registration/login.html`
e envia via POST. Quem recebe essa requisição é a
`LoginComDoisFatoresView`, em `usuarios/views.py` — uma versão
personalizada da tela de login padrão do Django.

### 3. Conferência da senha

O Django compara a senha digitada com o hash salvo no banco, usando o
algoritmo Argon2id configurado em `usuarios/hashers.py`.

- **Senha incorreta:** o formulário retorna com erro, sem revelar se o
  problema foi o usuário ou a senha (evita dar pistas para ataques).
- **Senha correta:** segue para o passo 4.

### 4. Verificação se o usuário tem 2FA ativado

A `LoginComDoisFatoresView` consulta o model `DispositivoTOTP`
(`dois_fatores/models.py`) para ver se existe um dispositivo
**confirmado** vinculado a esse usuário.

- **Sem 2FA confirmado:** o login é concluído imediatamente
  (`super().form_valid(form)`), e o usuário vai direto para a página
  inicial.
- **Com 2FA confirmado:** o login **não** é concluído ainda. O sistema
  guarda o ID do usuário numa chave temporária da sessão
  (`usuario_pendente_id`) e redireciona para a tela de verificação do
  código.

### 5. Digitação do código de 6 dígitos

Na tela `templates/dois_fatores/verificar.html`, o usuário digita o
código atual mostrado pelo app autenticador (Google Authenticator,
Authy, etc.).

### 6. Conferência do código

A view `verificar`, em `dois_fatores/views.py`, usa a biblioteca
`pyotp` para gerar o código esperado naquele momento a partir do
segredo salvo no banco, e compara com o que o usuário digitou
(com uma pequena margem de tolerância de tempo, `valid_window=1`).

- **Código incorreto:** mensagem de erro, o usuário continua na tela
  de verificação (ainda não está logado).
- **Código correto:** só agora o sistema chama `login()` de verdade,
  remove a marca temporária da sessão, e o usuário é enviado para a
  página inicial.

### 7. Após o login (qualquer um dos dois caminhos)

Assim que o `login()` do Django é chamado (seja no passo 4, sem 2FA,
ou no passo 6, com 2FA), o sinal `user_logged_in` dispara a função
`gravar_inicio_da_sessao` (`usuarios/signals.py`), que registra o
horário do início da sessão. Esse horário é usado depois pelo
`TimeoutAbsolutoMiddleware` (`usuarios/middleware.py`) para encerrar
a sessão automaticamente após o tempo máximo configurado, mesmo que o
usuário continue ativo.

## Por que o login não é finalizado antes do código do 2FA

Um ponto importante da implementação: quando o usuário tem 2FA
ativado, a função `login()` do Django **só é chamada depois do código
certo**. Isso significa que, tecnicamente, ninguém está "autenticado"
enquanto só tiver passado pela senha — mesmo que um invasor descubra a
senha de alguém, ele ainda não consegue acessar o sistema sem o
código do 2FA. Esse comportamento está coberto pelos testes em
`dois_fatores/tests.py` (classe `TesteLoginComDoisFatores`).

## Ativação do 2FA (fluxo separado)

Para ativar o 2FA, o usuário já precisa estar logado (rota
`dois-fatores/cadastrar/`, protegida por `@login_required`). O sistema
gera um segredo TOTP novo e mostra um link de provisionamento (que
pode ser escaneado por um app autenticador) e o próprio segredo em
texto. O usuário confirma digitando o primeiro código gerado; só
depois disso o dispositivo fica marcado como `confirmado = True` e
passa a ser exigido nos próximos logins.
