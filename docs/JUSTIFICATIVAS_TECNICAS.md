# Justificativas Técnicas de Segurança (Issue 1.12)

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
calcular o hash. Isso torna inviável testar milhões de senhas por
segundo, como seria possível com algoritmos mais antigos (MD5, SHA-1)
ou até mesmo PBKDF2 puro. Os parâmetros da OWASP equilibram essa
resistência com um tempo de resposta de login aceitável (poucas
centenas de milissegundos), já que o sistema roda em notebooks comuns
durante o desenvolvimento e a apresentação.

Como reforço, os hashers antigos (PBKDF2) continuam disponíveis em
`PASSWORD_HASHERS` apenas para compatibilidade. Todo hash **novo**
usa Argon2id.

## 2. Autenticação em dois fatores (2FA) com TOTP

**Onde:** `dois_fatores/models.py`, `dois_fatores/views.py`

O 2FA usa TOTP (Time-based One-Time Password, biblioteca `pyotp`) em
vez de outras abordagens, como código por SMS ou e-mail.

**Por quê:** TOTP não depende de nenhum serviço externo (SMS, e-mail)
para funcionar. O código é gerado localmente no celular do usuário a
partir de um segredo compartilhado, então não existe o risco de
interceptação de SMS (SIM swapping) nem dependência de terceiros para
autenticação. É o mesmo padrão usado por Google, GitHub e a maioria
dos sistemas com 2FA hoje.

**Por que o login não conclui antes do código certo:** a função
`login()` do Django só é chamada depois da verificação do TOTP
(ver `dois_fatores/views.py` e `FLUXO_AUTENTICACAO.md`). Isso garante
que a senha sozinha nunca é suficiente para autenticar quem tem 2FA
ativado. Mesmo que um invasor descubra a senha de alguém, ainda
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
nunca expiraria, e é exatamente isso que acontece quando uma sessão é
roubada e usada aos poucos, de propósito, para não parecer inativa.
Limitar o tempo total reduz a janela de uso de uma sessão
comprometida, independentemente de atividade.

**Comportamento fail-closed:** se por qualquer motivo a marca de início
da sessão não foi gravada, o middleware trata a sessão como inválida
(força novo login) em vez de assumir que ela não tem limite. Está
coberto pelo teste `test_sessao_sem_marca_de_inicio_e_tratada_como_expirada`
em `usuarios/tests.py`.

## 4. Logout que invalida a sessão no servidor

**Onde:** comportamento padrão do `LogoutView` do Django, testado em
`usuarios/tests.py`

O logout não apenas "esconde" a sessão no navegador, ele remove a
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
  tentativas com aquele usuário são recusadas (mesmo com a senha
  correta) até o bloqueio expirar.
- **Atraso progressivo:** cada tentativa errada aumenta o tempo de
  resposta do servidor (até um teto de 2,5 segundos), dificultando
  ataques automatizados que dependem de testar muitas senhas por
  segundo.

**Por que usar o cache em vez de uma tabela no banco:** contar
tentativas de login é, por natureza, um dado temporário: depois de
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
independentemente de onde vêm as tentativas, é a mesma lógica usada
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

## 7. Token de recuperação de senha com hash e uso único

**Onde:** `recuperacao_senha/models.py`, `recuperacao_senha/views.py`

O token de recuperação é gerado com `secrets.token_urlsafe(32)`, e só o
hash SHA-256 dele é salvo no banco. O token expira em 30 minutos e fica
inválido depois do primeiro uso.

**Por quê:** guardar só o hash segue a mesma lógica já aplicada à senha
do usuário. Se o banco vazar, ninguém consegue reconstruir o token
original a partir do hash e resetar a senha de outra pessoa.
`secrets.token_urlsafe` usa o CSPRNG do sistema operacional, o que torna
o token impossível de adivinhar por força bruta ou por um contador
previsível. O prazo de 30 minutos e a invalidação após o uso reduzem a
janela de um token roubado (de um e-mail interceptado, por exemplo) a
uma única tentativa dentro de um tempo curto.

**Por que a resposta é sempre genérica:** tanto a tela de solicitação
quanto a de redefinição respondem da mesma forma, independente do
motivo real (usuário não existe, token expirado, já usado ou
inexistente). Ninguém de fora descobre, testando respostas, quais
contas existem ou se um token específico já foi usado (enumeração de
contas/tokens).

## 8. Log de eventos de recuperação de senha

**Onde:** `config/settings.py` (`LOGGING`), `recuperacao_senha/views.py`

Toda solicitação de recuperação e todo resultado do processo (sucesso
ou falha, com o motivo) são registrados em um logger dedicado,
`seguranca.recuperacao_senha`, que grava no console e em
`logs/seguranca.log` (arquivo local, fora do controle de versão).

**Por quê:** um log de segurança só serve como registro se persistir
depois que a janela do terminal fechar. Por isso o log vai também para
um arquivo, além do console.

**Por que o nome do logger é hierárquico
(`seguranca.recuperacao_senha`):** a configuração de handlers fica
centralizada no logger pai `seguranca`, em `config/settings.py`. Um
logger futuro para outro assunto (ex: `seguranca.dois_fatores`) herda
os mesmos handlers automaticamente, sem repetir configuração, e cada
linha do log já mostra de qual parte do sistema veio o evento.

**Por que o motivo da falha vai pro log, mas não pro usuário:** o time
precisa do motivo real (token inexistente, expirado, já usado ou
confirmação de senha errada) para investigar um incidente depois. Como
esse motivo não pode aparecer na resposta ao usuário (quebraria a
proteção contra enumeração), o model `TokenRecuperacaoSenha` expõe um
método separado, `buscar_com_motivo`, usado só pela view para alimentar
o log, enquanto o restante do fluxo continua usando `validar`, que
devolve só o registro ou `None`.

## 9. TLS/HTTPS obrigatório em produção

**Onde:** `config/settings.py`

Em produção (`DEBUG=False`), `SECURE_SSL_REDIRECT`,
`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` e `SECURE_HSTS_SECONDS`
ficam ativados. Em desenvolvimento (`DEBUG=True`) continuam desligados,
porque o servidor local roda em HTTP simples.

**Por que usar as configurações prontas do Django, em vez de escrever
um middleware próprio:** o Django já resolve isso de forma correta e
testada por uma comunidade enorme há anos. Escrever um redirecionamento
HTTP→HTTPS na mão só adicionaria uma chance de erro sem nenhum ganho
real.

**Por que `SECURE_HSTS_PRELOAD` e `SECURE_HSTS_INCLUDE_SUBDOMAINS`
além do `SECURE_HSTS_SECONDS`:** o HSTS sozinho (`SECURE_HSTS_SECONDS`)
só protege depois da primeira visita — a primeira requisição ainda pode
ir por HTTP. `INCLUDE_SUBDOMAINS` estende a proteção pra qualquer
subdomínio, e `PRELOAD` permite cadastrar o domínio numa lista mantida
pelos navegadores, que já bloqueia HTTP mesmo na primeira visita. Como
o projeto ainda não tem domínio de produção, essas duas flags ficam
prontas mas o cadastro na lista de preload em si é um passo manual
futuro, fora do escopo do código.

## 10. AES-GCM para o segredo do 2FA

**Onde:** `dois_fatores/cripto.py`

O segredo do TOTP é cifrado com AES-GCM, usando uma chave de 256 bits
guardada em `CHAVE_CIFRAGEM_2FA` (variável de ambiente).

**Por que AES-GCM e não outro modo de AES (ex: CBC):** GCM é um modo
*autenticado* — além de cifrar, ele gera uma tag que comprova que o
dado não foi alterado. Se alguém adulterar um único byte do segredo
cifrado no banco, a decifragem falha explicitamente, em vez de devolver
um segredo TOTP corrompido silenciosamente (o que geraria códigos
errados sem nenhum aviso de que algo está errado).

**Por que um nonce novo a cada cifragem:** AES-GCM exige que o par
(chave, nonce) nunca se repita — reusar um nonce com a mesma chave
enfraquece a cifra seriamente. Por isso `cripto.cifrar` gera um nonce
aleatório novo (`os.urandom`) toda vez e guarda ele junto do resultado,
já que o nonce não precisa ser secreto, só único.

## 11. Cadeia de HMAC para proteger o log de segurança

**Onde:** `auditoria/integridade.py`, ligado em `config/settings.py`
(`LOGGING`). Detalhes e limites em `INTEGRIDADE_LOGS.md`.

Cada linha do log recebe um HMAC-SHA256 calculado sobre o próprio texto
e sobre o HMAC da linha anterior.

**Por que HMAC e não um hash simples (SHA-256 puro):** com hash sem
chave, quem consegue editar o arquivo também consegue recalcular todos
os hashes depois da alteração, e a cadeia volta a parecer válida. O HMAC
depende de uma chave secreta que não está no servidor de arquivos nem no
código, então quem altera o log não consegue gerar assinaturas válidas.

**Por que encadear, em vez de assinar cada linha sozinha:** com
assinatura independente por linha, apagar uma linha inteira (texto e
assinatura juntos) não deixaria rastro, porque todas as outras continuam
válidas. No encadeamento, cada assinatura depende da anterior, então
remover ou reordenar linhas quebra a verificação.

**Por que um handler, e não mudar cada `logger.info()`:** o handler
fica no logger pai `seguranca`. Todo evento de segurança, inclusive os
que outros integrantes forem criando, passa por ele automaticamente.
Proteger evento por evento dependeria de ninguém esquecer.

**Por que usar `hmac` e `hashlib` da biblioteca padrão:** são
implementações mantidas e revisadas junto com o próprio Python. O
projeto só monta a cadeia, sem implementar nenhuma primitiva
criptográfica por conta própria. A comparação usa `hmac.compare_digest`,
que leva o mesmo tempo independente de onde os valores diferem, pra não
dar pista sobre a assinatura correta.

**Por que uma chave separada da `CHAVE_CIFRAGEM_2FA`:** cada chave com
uma única finalidade. Se uma vazar, a outra proteção continua valendo.

**Por que a tela de verificação é só para administradores:** o
resultado mostra em qual linha o log foi alterado, informação que
ajudaria um invasor a testar se conseguiu esconder rastros.
