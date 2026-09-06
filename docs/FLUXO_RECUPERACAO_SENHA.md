# Fluxo de Recuperação de Senha — CirculaGov (Requisitos 2.1 a 2.7)

Este documento descreve, passo a passo, como funciona a recuperação de
senha no CirculaGov, incluindo a geração do token, a troca de senha e o
registro em log de cada etapa.

## Visão geral

A recuperação acontece em duas telas:

1. **Solicitação** — usuário informa o nome de usuário e recebe, se a
   conta existir, um e-mail com um link de redefinição.
2. **Redefinição** — usuário acessa o link recebido e escolhe uma senha
   nova.

## Passo a passo

### 1. Solicitação da recuperação

O usuário acessa `/recuperar-senha/` e informa o nome de usuário na tela
`templates/recuperacao_senha/solicitar.html`. O POST é recebido pela view
`solicitar`, em `recuperacao_senha/views.py`.

### 2. Busca do usuário e geração do token

A view procura o usuário pelo `username` informado. Se existir, chama
`TokenRecuperacaoSenha.gerar(usuario)` (`recuperacao_senha/models.py`),
que:

- Gera um valor aleatório com `secrets.token_urlsafe(32)` (requisito 2.2),
  usando o CSPRNG do sistema operacional em vez de um gerador previsível.
- Salva no banco só o hash SHA-256 desse valor, nunca o valor em texto
  puro.
- Define a expiração em 30 minutos a partir da criação (requisito 2.3).

### 3. Envio do e-mail (ou ausência dele)

Se o usuário existir, `_enviar_email_recuperacao` monta o link de
redefinição e envia com `send_mail` (backend console em
desenvolvimento). Se o usuário não existir, nenhum e-mail é enviado, mas
a resposta ao usuário é idêntica nos dois casos (ver "Por que a resposta
é sempre igual").

### 4. Registro da solicitação em log

Antes de responder, a view registra o evento no logger
`seguranca.recuperacao_senha` (requisito 2.6), incluindo o username
informado, independentemente de ele existir ou não.

### 5. Acesso ao link de redefinição

O usuário abre o link recebido, que chama a view `redefinir` com o token
na URL. A view chama `TokenRecuperacaoSenha.buscar_com_motivo(token)`
(`recuperacao_senha/models.py`), que confere se o token existe, se já foi
usado (requisito 2.4) e se ainda está dentro do prazo de validade
(requisito 2.3).

- **Token inválido, expirado ou já usado:** a página `token_invalido.html`
  é exibida com status 400 (requisito 2.5), e o motivo real (qual das três
  causas) é registrado no log de segurança, mas nunca aparece na resposta
  ao usuário.
- **Token válido:** o formulário de nova senha é exibido.

### 6. Troca da senha

O usuário digita a senha nova duas vezes. Se as duas não conferem, a view
mostra um erro e registra a falha no log. Se conferem, a view chama
`set_password`, salva o usuário, marca o token como usado
(`registro.marcar_usado()`, requisito 2.4) e registra o sucesso no log
(requisito 2.7).

## Por que a resposta é sempre igual, exista ou não o usuário

A tela de solicitação sempre mostra a mesma mensagem de sucesso, e a
tela de redefinição sempre mostra a mesma página de erro para token
inexistente, expirado ou já usado. Isso evita enumeração de contas e de
tokens: quem está de fora não consegue descobrir, testando respostas, se
um usuário existe ou se um token específico já foi usado. Esse
comportamento está coberto pelos testes
`test_solicitar_nao_revela_se_usuario_existe` e
`test_token_expirado_usado_e_inexistente_mostram_a_mesma_pagina`, em
`recuperacao_senha/tests.py`.

## Por que o log sabe o motivo, mas o usuário nunca vê

O log de segurança (requisitos 2.6 e 2.7) precisa do motivo real de cada
falha (token inexistente, expirado, já usado ou confirmação de senha
errada) para que o time consiga investigar um incidente depois. Só que
esse mesmo motivo, se aparecesse na resposta ao usuário, quebraria a
proteção contra enumeração explicada acima. Por isso o model
`TokenRecuperacaoSenha` mantém dois métodos separados: `validar` (usado
pelo restante do fluxo, devolve só o registro ou `None`) e
`buscar_com_motivo` (usado só pela view, para alimentar o log). O motivo
nunca chega ao template, só ao logger.
