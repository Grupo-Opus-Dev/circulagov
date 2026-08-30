# Justificativas Técnicas — Segurança (Issue 1.12)

Este documento reúne o "porquê" por trás das principais decisões de
segurança do CirculaGov, complementando o `FLUXO_AUTENTICACAO.md`
(que explica o "como funciona").

## 1. Hash de senha com Argon2id

**Onde:** `usuarios/hashers.py`

O projeto usa Argon2id como algoritmo de hash de senha, com os
parâmetros recomendados pelo OWASP Password Storage Cheat Sheet
(2024): `memory_cost=19 MiB`, `time_cost=2`, `parallelism=1`.

**Por quê:** o Argon2 é resistente a ataques com GPU/hardware
especializado porque exige memória (não só tempo de CPU) para
calcular o hash — isso torna inviável testar milhões de senhas por
segundo, como seria possível com algoritmos mais antigos (MD5, SHA-1)
ou até mesmo PBKDF2 puro. Os parâmetros da OWASP equilibram essa
resistência com um tempo de resposta de login aceitável (poucas
centenas de milissegundos), já que o sistema roda em notebooks comuns
durante o desenvolvimento e a apresentação.

Como reforço, os hashers antigos (PBKDF2) continuam disponíveis em
`PASSWORD_HASHERS` apenas para compatibilidade — todo hash **novo**
usa Argon2id.

## 2. Autenticação em dois fatores (2FA) com TOTP

**Onde:** `dois_fatores/models.py`, `dois_fatores/views.py`

O 2FA usa TOTP (Time-based One-Time Password, biblioteca `pyotp`) em
vez de outras abordagens, como código por SMS ou e-mail.

**Por quê:** TOTP não depende de nenhum serviço externo (SMS, e-mail)
para funcionar — o código é gerado localmente no celular do usuário a
partir de um segredo compartilhado, então não existe o risco de
interceptação de SMS (SIM swapping) nem dependência de terceiros para
autenticação. É o mesmo padrão usado por Google, GitHub e a maioria
dos sistemas com 2FA hoje.

**Por que o login não conclui antes do código certo:** a função
`login()` do Django só é chamada depois da verificação do TOTP
(ver `dois_fatores/views.py` e `FLUXO_AUTENTICACAO.md`). Isso garante
que a senha sozinha nunca é suficiente para autenticar quem tem 2FA
ativado — mesmo que um invasor descubra a senha de alguém, ainda
precisa do código do app autenticador.

**Por que o 2FA é opcional:** para o MVP, exigir 2FA de todo mundo
adicionaria fricção desnecessária no cadastro inicial. A abordagem
opcional (usuário ativa quando quiser) segue o padrão usado por
sistemas conhecidos e ainda assim eleva a segurança de quem ativar.

## 3. Timeout absoluto de sessão

**Onde:** `usuarios/middleware.py`, configurado via
`TEMPO_MAXIMO_SESSAO_SEGUNDOS` em `config/settings.py`

O Django, sozinho, só cobre timeout por **inatividade**
(`SESSION_COOKIE_AGE` + `SESSION_SAVE_EVERY_REQUEST`). O projeto
adiciona um `TimeoutAbsolutoMiddleware` para encerrar a sessão após um
tempo máximo desde o login, **mesmo que o usuário esteja ativo o
tempo todo**.

**Por quê:** sem esse timeout absoluto, uma sessão em uso contínuo
nunca expiraria — e é exatamente isso que acontece quando uma sessão é
roubada e usada aos poucos, de propósito, para não parecer inativa.
Limitar o tempo total reduz a janela de uso de uma sessão
comprometida, independentemente de atividade.

**Comportamento fail-closed:** se por qualquer motivo a marca de início
da sessão não foi gravada, o middleware trata a sessão como inválida
(força novo login) em vez de assumir que ela não tem limite — está
coberto pelo teste `test_sessao_sem_marca_de_inicio_e_tratada_como_expirada`
em `usuarios/tests.py`.

## 4. Logout que invalida a sessão no servidor

**Onde:** comportamento padrão do `LogoutView` do Django, testado em
`usuarios/tests.py`

O logout não apenas "esconde" a sessão no navegador — ele remove a
linha correspondente da tabela de sessões no banco de dados. Um cookie
antigo, mesmo reaproveitado manualmente depois do logout, não
consegue mais autenticar (`test_cookie_antigo_nao_reautentica_depois_do_logout`).

**Por quê:** se a sessão só fosse invalidada no lado do cliente
(apagando o cookie), um cookie roubado antes do logout continuaria
válido para sempre no servidor. Invalidar no banco fecha essa brecha.

## 5. Proteção contra força bruta no login

**Onde:** `usuarios/seguranca.py`, usado em `usuarios/views.py`

A proteção combina três camadas, todas usando o sistema de **cache**
nativo do Django (`django.core.cache`) em vez de uma tabela nova no
banco:

- **Contagem de tentativas (rate limit):** cada senha errada soma uma
  falha, associada ao nome de usuário digitado.
- **Bloqueio temporário:** após 5 falhas em 15 minutos, novas
  tentativas com aquele usuário são recusadas — mesmo com a senha
  correta — até o bloqueio expirar.
- **Atraso progressivo:** cada tentativa errada aumenta o tempo de
  resposta do servidor (até um teto de 2,5 segundos), dificultando
  ataques automatizados que dependem de testar muitas senhas por
  segundo.

**Por que usar o cache em vez de uma tabela no banco:** contar
tentativas de login é, por natureza, um dado temporário — depois de
alguns minutos, a informação não importa mais. Usar o cache (que já
vem pronto no Django, sem precisar de migração) evita crescer o banco
de dados com registros descartáveis e mantém a solução mais simples.

**Por que os números escolhidos (5 tentativas / 15 minutos / até
2,5s):** o objetivo é equilibrar segurança com experiência do usuário
legítimo. Um usuário real que erra a senha por engano dificilmente
erra mais de 4-5 vezes seguidas; já um ataque automatizado, que
precisaria de milhares de tentativas para ter chance de acertar uma
senha com Argon2, se torna impraticável com esse limite combinado ao
atraso progressivo.

**Por que o bloqueio é por username e não por IP:** bloquear por IP
sozinho permitiria que um invasor usasse vários IPs diferentes (bem
comum em ataques reais) para contornar o limite. Bloquear por
username garante que aquela conta específica fica protegida
independentemente de onde vêm as tentativas — é a mesma lógica usada
por grande parte dos sistemas de login com proteção anti-força-bruta.

## 6. Model de usuário customizado

**Onde:** `usuarios/models.py` (`AUTH_USER_MODEL = 'usuarios.Usuario'`)

O projeto estende `AbstractUser` do Django em vez de usar o model de
usuário padrão.

**Por quê:** trocar o model de autenticação depois que o projeto já
está em produção é uma migração complexa e arriscada no Django. Usar
um model customizado desde o início, mesmo que hoje ele não adicione
campos extras, garante flexibilidade para o futuro (ex: vínculo com
município/biblioteca) sem esse risco.
