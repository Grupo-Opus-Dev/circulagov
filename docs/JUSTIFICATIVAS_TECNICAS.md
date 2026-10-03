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
precisa do código do app autenticador. Isso vale para todo caminho de
entrada porque o login do admin também passa por aqui (seção 12).

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

A proteção combina três camadas, com o contador numa tabela própria do
banco (`ContadorDeTentativas`, em `usuarios/contadores.py`):

- **Contagem de tentativas (rate limit):** cada senha errada soma uma
  falha, associada ao nome de usuário digitado.
- **Bloqueio temporário:** após 5 falhas em 15 minutos, novas
  tentativas com aquele usuário são recusadas (mesmo com a senha
  correta) até o bloqueio expirar.
- **Atraso progressivo:** cada tentativa errada aumenta o tempo de
  resposta do servidor (até um teto de 2,5 segundos), dificultando
  ataques automatizados que dependem de testar muitas senhas por
  segundo.

**Por que o contador fica no banco, e não no cache.** Contar tentativas é um
dado temporário, e a primeira versão usava o cache do Django. Em produção o
Gunicorn roda vários processos, então o contador precisa ser único entre
eles, o que levou ao cache em tabela do PostgreSQL. Isso se mostrou
insuficiente por dois motivos, e o contador passou a ser uma tabela própria:

- **Contagem perdida.** O `incr()` do cache em banco lê o valor e depois
  grava, em passos separados, e a documentação do Django não o garante
  atômico. Duas falhas simultâneas podiam contar como uma. Agora cada soma
  trava a linha do contador (`SELECT ... FOR UPDATE`) dentro de uma
  transação, e a criação simultânea da mesma chave é tratada. Os testes de
  `TesteContadoresAtomicos` disparam as falhas em threads ao mesmo tempo, e
  quatro deles falham quando o travamento é removido.
- **Descarte por ordem alfabética.** O cache em banco apagava um terço das
  entradas, por ordem alfabética da chave, ao passar de um teto de entradas
  (300 por padrão), e quem tentava senhas contra uma conta podia zerar o
  próprio bloqueio mandando tentativas com nomes inventados. A tabela
  própria não descarta nada: as linhas vencidas são apagadas na criação da
  linha seguinte. `test_muitas_chaves_inventadas_nao_apagam_o_contador_da_vitima`
  cobre isso.

A chave de cada contador é um hash (SHA-256), então nomes de usuário e
endereços não ficam em claro na tabela e um nome de usuário gigante não
quebra o campo. A janela é guardada em segundos desde 1970, o que a deixa
independente de fuso.

Foi escolhido em vez do Redis porque o banco já existe, e subir mais um
serviço só para isso não se justificava no tamanho do projeto. O custo é uma
ida ao banco por tentativa de login, aceitável para o volume do sistema.

A defesa complementar é um limite de requisições por endereço no nginx. A
configuração, com teste automatizado, está em `deploy/nginx/`, foi instalada
no nginx do servidor em 03/10/2026 e conferida de fora, como descrito em
[DEPLOY.md](DEPLOY.md). Ela encarece o ataque, mas não o elimina: quem usa
muitos endereços passa por ela.

**Duas telas não têm trava por conta no código.** A verificação do código do
segundo fator e o pedido de recuperação de senha não contam tentativas. Só o
limite por endereço do nginx as protege, e ele reduz a velocidade sem impedir
o ataque. Fica registrado como lacuna, e não como risco resolvido.

O ponto foi descoberto ao documentar o deploy, depois de o contador já
estar em produção.

**Por que os números escolhidos (5 tentativas / 15 minutos / até
2,5s):** o objetivo é equilibrar segurança com experiência do usuário
legítimo. Um usuário real que erra a senha por engano dificilmente
erra mais de 4-5 vezes seguidas; já um ataque automatizado, que
precisaria de milhares de tentativas para ter chance de acertar uma
senha com Argon2, se torna impraticável com esse limite combinado ao
atraso progressivo.

**Por que o bloqueio é por usuário e endereço, com um teto por conta:**
bloquear só por endereço deixaria um invasor trocar de endereço (comum em
ataques reais) para contornar o limite. Bloquear só por usuário deixaria
qualquer pessoa trancar a conta de outra apenas errando a senha dela. Por
isso há dois contadores:

- por par (usuário, endereço): 5 falhas em 15 minutos bloqueiam aquele
  endereço para aquele usuário, sem afetar quem acessa de outro lugar;
- por conta, somando todos os endereços: 25 falhas em 15 minutos bloqueiam
  a conta para todos. O teto é alto para que o dono da conta não seja
  trancado por um ou dois atacantes, e baixo o bastante para que tentar
  senhas de muitos endereços deixe de compensar.

O endereço vem do cabeçalho `X-Real-IP`, que o nginx sobrescreve com o
endereço real da conexão (`CABECALHO_IP_DO_CLIENTE` em `config/settings.py`).
O cabeçalho não pode vir do cliente, porque o nginx o substitui sempre.

**Por que o bloqueio não é renovado enquanto dura:** a contagem começa na
primeira falha e, ao chegar no limite, recomeça por 15 minutos cheios.
Tentativas feitas durante o bloqueio não somam. Antes, cada uma delas
reiniciava o prazo, e quem continuava tentando, inclusive o próprio dono da
conta, ficava bloqueado indefinidamente. Os testes estão em
`TesteBloqueioDeLoginPorEndereco`, em `usuarios/tests.py`.

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

## 12. O admin do Django usa o login da aplicação

**Onde:** `usuarios/admin_site.py`, `usuarios/admin_config.py` e `INSTALLED_APPS`
em `config/settings.py`

O admin do Django traz um login próprio, com formulário e rota próprios
(`/admin/login/`). Esse login não passa pelo segundo fator nem pelo bloqueio por
tentativas, que existem só no login da aplicação. Resultado, comprovado por
teste: quem tinha a senha de uma conta de gestão entrava no `/admin/` sem o
código, mesmo com o 2FA ativo, e podia tentar senhas sem limite. O limite do
nginx também não cobria esse caminho.

O que a documentação afirmava, que a senha sozinha nunca basta para quem tem
2FA, valia só para o login da aplicação.

**A correção** troca o site de administração por um que não autentica ninguém. O
`/admin/login/` passou a só redirecionar para o login da aplicação, e o admin
aceita a sessão que sai de lá. Assim ele herda o segundo fator e o bloqueio por
tentativas, sem duplicar código. A troca usa o mecanismo documentado do Django
para substituir o site padrão, e não altera tabelas.

**Por que não só desligar o `/admin/`:** ele continua útil para consultar e
corrigir dados que a área de gestão não cobre. Desligar tiraria essa
ferramenta sem necessidade, agora que o contorno acabou.

**O que continua valendo.** O 2FA segue opcional: uma conta de gestão que nunca o
ativou entra no admin só com a senha, como entra na aplicação. Exigir o segundo
fator de toda conta de gestão seria uma decisão de política, e não foi tomada.

## 13. Trava de tentativas e prazo no segundo fator

**Onde:** `dois_fatores/limite.py` e `dois_fatores/views.py`

O código TOTP tem 6 dígitos. Quem já sabe a senha de uma conta chega na tela
do código, e sem trava poderia tentar muitos códigos até acertar o da janela
de 30 segundos. A etapa também não expirava: a sessão com a senha aceita
continuava aberta enquanto houvesse requisições.

**Por que a trava é por conta e não por endereço:** nessa etapa a conta já
está identificada pela senha certa. Contar por endereço deixaria quem troca de
endereço ganhar tentativas novas. Como o bloqueio só é alcançável por quem
acertou a senha, ele não serve para trancar a conta de um desconhecido.

**Por que 5 tentativas em 15 minutos:** a chance de acertar um código de 6
dígitos em 5 tentativas é de 5 em 1 milhão por janela, e dá folga para quem
erra a digitação ou o relógio do celular está um pouco fora.

**Por que o bloqueio não é renovado enquanto dura:** durante o bloqueio a
verificação nem confere o código, e a falha não soma. Se somasse, cada
tentativa reiniciaria o prazo. Nem o código certo entra durante o bloqueio, e
ele também vale se a pessoa passar pela senha de novo, porque o contador está
na conta e não na sessão.

**Por que a etapa expira em 5 minutos:** é tempo de sobra para abrir o app e
digitar seis números. Passado o prazo, a pessoa volta ao login. O prazo evita
que uma sessão esquecida na tela do código continue valendo.

Os testes estão em `TesteTravaDoSegundoFator`, em `dois_fatores/tests.py`.

## 14. Recuperação de senha: uso único atômico e limite de e-mails por conta

**Onde:** `recuperacao_senha/models.py` e `recuperacao_senha/views.py`

**Uso único.** A versão anterior conferia o token, trocava a senha e só então
o marcava como usado, sem transação. Dois pedidos simultâneos com o mesmo link
passavam os dois pela conferência. Agora o token é consumido por um
`UPDATE ... WHERE usado_em IS NULL AND expira_em >= agora`, e o banco decide
quem ganhou: só quem alterou uma linha segue. O consumo e a troca da senha
ficam na mesma transação, então uma falha ao gravar a senha devolve o token.
A senha é salva só no campo `password` (`update_fields`), pra não regravar o
restante do usuário com dados que podem ter mudado.

**Por que não só um `select_for_update`:** funcionaria, mas o UPDATE condicional
é um passo só, não depende de lembrar de travar a linha antes de ler e deixa
a decisão no banco.

**Limite de e-mails.** O nginx limita por endereço. Quem usa muitos endereços
ainda poderia encher a caixa de uma pessoa e gastar a cota diária de envios da
conta. O limite por conta é de 3 e-mails por hora, contados na mesma tabela
de contadores, com janela fixa. Os pedidos além disso recebem a mesma resposta genérica de
sempre, para não revelar que a conta existe, e vão para o log. O convite da
gestão não entra nessa conta, porque é uma ação de um gestor autenticado, e
não um pedido anônimo.

## 15. CSS sem CDN e política de conteúdo (CSP)

**Onde:** `static/`, `templates/base.html`, `usuarios/middleware.py`
(`PoliticaDeConteudoMiddleware`) e `usuarios/test_csp.py`

**Por que sair do CDN do Tailwind:** o script do CDN monta o CSS no navegador
e precisa de `unsafe-eval` e de estilo inline para funcionar, o que anula a
principal proteção de uma CSP. Além disso, ele roda com todos os poderes de
uma página de login e de 2FA, vindo de um domínio que o projeto não controla,
sem verificação de integridade. O próprio Tailwind desaconselha o uso em
produção. O CSS gerado tem cerca de 15 KB, bem menos que o script.

**Como o CSS foi gerado:** com as classes realmente usadas nos templates e nas
strings `CLASSE_*` do Python, passando por esse mesmo CDN uma única vez, na
versão 3.4.17, e copiando o resultado para `static/css/tailwind.css`. Ele é
versionado no repositório, então o que roda em produção é o que foi revisado.

**Por que um teste de cobertura de classes:** sem o CDN, uma classe nova num
template fica sem estilo e ninguém percebe. `TesteCssDoTailwindVersionado`
lê as classes dos templates e confere se cada uma tem regra no arquivo. Se
falhar, o CSS precisa ser gerado de novo.

**A política:** `default-src 'self'`, `script-src 'self'`,
`style-src 'self' https://fonts.googleapis.com`,
`font-src https://fonts.gstatic.com`, `img-src 'self' data:`,
`object-src 'none'`, `base-uri 'self'`, `form-action 'self'` e
`frame-ancestors 'none'`. Não há `unsafe-inline` nem `unsafe-eval`.

**Por que mexer nos templates:** a política proíbe script dentro do HTML.
O script da tela de novo usuário foi para `static/js/novo-usuario.js`, e o
`onsubmit` da confirmação de remoção do 2FA virou o atributo
`data-confirmar`, tratado por `static/js/confirmar.js`. O bloco `<style>` da
fonte foi para `static/css/circulagov.css`.

**Por que o Google Fonts ficou:** a fonte Inter já era carregada de lá.
Trazê-la para o servidor exige baixar e versionar os arquivos da fonte, o que
fica como melhoria. A política só libera estilo e fonte desse domínio, nunca
script.

**Por que `frame-ancestors 'none'`:** equivale ao `X-Frame-Options: DENY` que
o Django já envia, para os navegadores que seguem só a CSP.

**O admin do Django:** as telas dele usam apenas arquivos próprios em `static/`
e não precisaram de exceção. O teste `test_nenhuma_tela_depende_de_codigo_dentro_do_html`
percorre a aplicação e o admin procurando script, estilo e manipuladores de evento
escritos dentro do HTML.

## 16. Âncoras para o corte do final do log

**Onde:** `auditoria/integridade.py`, `auditoria/ancoras.py` e os comandos
`emitir_ancora` e `verificar_logs`

A cadeia de HMAC (seção 11) detecta alteração no meio do log, mas não o corte
do final: quem apaga as últimas linhas deixa uma cadeia menor e ainda válida.
Isso já era um limite documentado. A âncora o trata, dentro do que um sistema
sem servidor externo consegue.

**Por que âncora e não só guardar o último MAC:** o último MAC avisa se o
final mudou, mas não diz se o log foi só estendido. A âncora guarda também o
número da linha, então o log pode crescer e a âncora continua valendo: a
verificação exige apenas que a linha N ainda tenha a assinatura registrada.
Essa conferência também pega o log reescrito inteiro por quem tem a chave, com o
mesmo tamanho, o que a cadeia sozinha não pega.

**Por que a âncora é assinada:** ela é guardada em lugares onde outras
pessoas podem escrever, como e-mail e arquivos de texto. Sem assinatura, bastaria
inventar uma âncora com número de linhas absurdo para derrubar a verificação, ou
trocar uma verdadeira por uma antiga. A assinatura usa a chave do log e
`hmac.compare_digest`, como a cadeia.

**Por que uma âncora inválida reprova:** ignorá-la deixaria quem a adulterou
sem consequência.

**Por que o envio por e-mail:** a âncora só protege se estiver fora do
servidor que o atacante controla, e o projeto já tem e-mail configurado. Ela não
contém a chave nem texto do log, só um número, uma assinatura e uma data.

**O que a solução não resolve:** o que foi apagado depois da última âncora, e
a âncora guardada só no servidor, que cai junto. Por isso o comando avisa quando
não há âncora e a documentação pede a cópia externa. Agendar a emissão e guardar
as mensagens fica por conta de quem opera o servidor.

**Por que recusar emitir âncora de log adulterado ou vazio:** ancorar um
log já adulterado carimbaria o estrago como válido, e ancorar um log vazio
não prova nada.
