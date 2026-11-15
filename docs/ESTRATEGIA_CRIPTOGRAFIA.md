# Estratégia de Criptografia (Issue 3.7)

Este documento resume onde e como o CirculaGov usa criptografia hoje,
separando dado em trânsito de dado em repouso. As justificativas de
cada escolha estão em [`JUSTIFICATIVAS_TECNICAS.md`](JUSTIFICATIVAS_TECNICAS.md).

## Tabela resumo

| Dado protegido | Algoritmo | Onde no código | Chave usada |
|---|---|---|---|
| Senha do usuário | Argon2id | `usuarios/hashers.py` | Não aplicável, hash de mão única, sem chave |
| Segredo do 2FA (TOTP) em repouso | AES-GCM (256 bits) | `dois_fatores/cripto.py` | `CHAVE_CIFRAGEM_2FA` (variável de ambiente, `.env`) |
| RA do aluno em repouso | AES-GCM (256 bits), com índice HMAC-SHA256 para busca | `alunos/protecao.py` | `CHAVE_CIFRAGEM_2FA`, e uma chave derivada dela para o índice |
| Token de recuperação de senha | SHA-256 (hash) | `recuperacao_senha/models.py` | Não aplicável, hash de mão única, sem chave |
| Integridade do log de segurança | HMAC-SHA256 encadeado | `auditoria/integridade.py` | `CHAVE_INTEGRIDADE_LOGS` (variável de ambiente, `.env`) |
| Tráfego entre navegador e servidor | TLS 1.3 | `config/settings.py` | Certificado do servidor (fora do repositório) |

## 1. Argon2id para senha

**Onde:** `usuarios/hashers.py`, classe `Argon2PasswordHasherCirculaGov`.

**Parâmetros:** `time_cost=2`, `memory_cost=19*1024` KiB (19 MiB),
`parallelism=1`, os valores recomendados pelo OWASP Password Storage
Cheat Sheet (2024) para Argon2id.

**Por quê:** Argon2 é resistente a ataques com GPU ou hardware
especializado porque exige memória, não só tempo de CPU, para calcular
o hash. Isso torna inviável testar milhões de senhas por segundo, como
seria possível com algoritmos mais antigos (MD5, SHA-1) ou até PBKDF2
puro. É um hash de mão única: não existe chave, porque o sistema nunca
precisa recuperar a senha original, só conferir se a senha digitada
bate com o hash salvo. Detalhes do salt e do formato de armazenamento
estão em [`GESTAO_CREDENCIAIS.md`](GESTAO_CREDENCIAIS.md).

## 2. AES-GCM para o segredo do 2FA em repouso

**Onde:** `dois_fatores/cripto.py`, funções `cifrar` e `decifrar`.

**Parâmetros:** chave de 256 bits, guardada em `CHAVE_CIFRAGEM_2FA`
(variável de ambiente), e um nonce de 12 bytes gerado com `os.urandom`
a cada cifragem.

**Por quê:** diferente da senha, o sistema precisa ler o segredo do
2FA de volta para gerar o código TOTP esperado a cada login, então uma
função de hash de mão única não serve aqui, é preciso uma cifra
reversível com chave. GCM é um modo autenticado: além de cifrar, gera
uma tag que comprova que o dado não foi alterado. Se alguém adulterar
um byte do segredo cifrado no banco, a decifragem falha explicitamente,
em vez de devolver um segredo corrompido silenciosamente. O nonce
precisa ser novo a cada cifragem porque o par (chave, nonce) nunca pode
se repetir em AES-GCM, sob pena de enfraquecer a cifra, mas o nonce em
si não precisa ser secreto, só único, por isso é guardado junto do
resultado cifrado.

## 3. HMAC-SHA256 encadeado para integridade do log

**Onde:** `auditoria/integridade.py`, ligado em `config/settings.py`
(`LOGGING`). Detalhes de como verificar e os limites da proteção estão
em [`INTEGRIDADE_LOGS.md`](INTEGRIDADE_LOGS.md).

**Parâmetros:** HMAC-SHA256, chave de pelo menos 32 bytes em
`CHAVE_INTEGRIDADE_LOGS` (variável de ambiente), separada da
`CHAVE_CIFRAGEM_2FA`.

**Por quê:** cada linha do log recebe uma assinatura calculada sobre o
próprio texto e sobre a assinatura da linha anterior, formando uma
cadeia. Um hash simples (SHA-256 sem chave) não bastaria: quem consegue
editar o arquivo também conseguiria recalcular os hashes depois da
alteração, e a cadeia voltaria a parecer válida. O HMAC depende de uma
chave secreta que não fica no servidor de arquivos nem no código-fonte,
então quem altera o log não consegue gerar assinaturas válidas. O
encadeamento, em vez de uma assinatura independente por linha, garante
que apagar ou reordenar uma linha também quebra a verificação a partir
dali, não só a linha alterada.

## 4. SHA-256 para o token de recuperação de senha

**Onde:** `recuperacao_senha/models.py`, método `TokenRecuperacaoSenha._hash`.

**Por quê:** assim como a senha, o token só precisa ser *conferido*,
nunca lido de volta em texto puro, então também é um hash de mão única,
sem chave. Guardar só o hash segue a mesma lógica aplicada à senha do
usuário: se o banco vazar, ninguém consegue reconstruir o token
original a partir do hash e resetar a senha de outra pessoa. O valor
original é gerado com `secrets.token_urlsafe(32)` (CSPRNG do sistema
operacional), o que o torna impossível de adivinhar por força bruta.
Ciclo de vida completo (expiração, uso único) em
[`GESTAO_CREDENCIAIS.md`](GESTAO_CREDENCIAIS.md).

## 5. Dado em trânsito (rede)

Toda comunicação entre o navegador e o servidor é protegida por
TLS/HTTPS. Em produção (`DEBUG=False`):

- `SECURE_SSL_REDIRECT` redireciona qualquer requisição HTTP pra HTTPS.
- `SESSION_COOKIE_SECURE` e `CSRF_COOKIE_SECURE` impedem que os cookies
  de sessão e CSRF trafeguem fora de uma conexão cifrada.
- `SECURE_HSTS_SECONDS` avisa o navegador pra nunca mais tentar HTTP
  nesse domínio, nem que o usuário digite a URL errada.

Evidência de que isso funciona na prática, incluindo o protocolo
`TLSv1.3` observado na conexão, está em
[`EVIDENCIA_TLS.md`](EVIDENCIA_TLS.md).

## 6. Dado em repouso (banco de dados e arquivo de log)

Quatro estratégias diferentes, dependendo do que o sistema precisa fazer
com o dado:

**Hash, sem chave (senha e token de recuperação):** dado que só precisa
ser *conferido*, nunca lido de volta em texto puro. Usa Argon2id
(senha) ou SHA-256 (token), funções de mão única, sem chave, sem como
reverter.

**Cifragem reversível, com chave (segredo do 2FA):** dado que o próprio
sistema precisa ler de volta pra gerar o código TOTP e comparar com o
que o usuário digita, então precisa de uma cifra reversível com chave:
AES-GCM. A chave fica fora do banco e fora do código-fonte, na variável
de ambiente `CHAVE_CIFRAGEM_2FA` (mesmo padrão já usado pra
`SECRET_KEY` e pra senha do PostgreSQL).

**Cifragem reversível com índice (RA do aluno):** o RA é o
identificador do aluno na rede estadual e aparece na gestão e na
exportação dos dados do titular, então também precisa voltar ao texto
original. Fica cifrado com AES-GCM, pela mesma rotina do 2FA, com o
contexto `circulagov:aluno.ra` como dado associado: um RA cifrado não
decifra se for colado no lugar de outro campo. Como o valor cifrado muda
a cada gravação, ele não serve para buscar nem para garantir que o RA é
único. Para isso existe a coluna `ra_indice`, um HMAC-SHA256 do RA com
uma chave derivada da chave de cifragem: o mesmo RA dá sempre o mesmo
índice, e sem a chave não se volta ao RA. O custo é que a busca passa a
achar só o RA completo, não parte dele. Testes em `alunos/tests.py`
(`TesteRACifradoEmRepouso` e `TesteMigracaoQueCifraORA`).

A chave fica no mesmo servidor do banco. A cifragem protege contra quem
obtém só o banco ou uma cópia dele (um dump, um volume copiado); quem
controla o servidor inteiro lê a chave e decifra. O nome de usuário da
conta também pode ser o próprio RA, se quem criou a conta escolheu
assim, e esse campo não é cifrado porque é usado no login.

**Assinatura encadeada, com chave (log de segurança):** dado que
precisa ser lido em texto puro (é um log, alguém precisa poder ler as
linhas), mas cuja integridade precisa ser verificável depois. Não é
hash nem cifragem, é assinatura: o texto continua legível, e o
HMAC-SHA256 ao final de cada linha só serve pra provar que ela não foi
alterada desde que foi gravada.

## 6.1 Classificação dos campos e proteção de cada um

Resposta ao parecer da v1.5.1 (item 3.4), que pediu para dizer quais dados
pessoais são cifrados em repouso e justificar os demais. Categorias:
**credencial** (serve para entrar no sistema), **segredo** (gera ou confere
uma credencial), **identificador** (identifica a pessoa) e **metadado**
(dado de controle gerado pelo sistema).

| Tabela e campo | Categoria | Proteção em repouso | Por quê |
|---|---|---|---|
| `usuarios_usuario.password` | Credencial | Hash Argon2id | Só precisa ser conferida, nunca lida de volta |
| `dois_fatores_dispositivototp.segredo_cifrado` | Segredo | AES-GCM | O sistema precisa ler de volta para gerar o código |
| `recuperacao_senha_tokenrecuperacaosenha.token_hash` | Credencial temporária | Hash SHA-256 | Só precisa ser conferido |
| `alunos_aluno.ra_cifrado` | Identificador | AES-GCM, com índice HMAC-SHA256 (`ra_indice`) para busca | É o identificador oficial do aluno na rede estadual, o dado que mais identifica a pessoa fora do sistema |
| `alunos_aluno.nome_completo` | Identificador | Acesso restrito ao banco | Ver abaixo |
| `usuarios_usuario.username` | Identificador | Acesso restrito ao banco | Usado no login: precisa ser buscado pelo valor exato a cada tentativa |
| `usuarios_usuario.email` | Identificador | Acesso restrito ao banco | Usado para enviar o e-mail de recuperação e conferido na gestão |
| `usuarios_usuario.first_name`, `last_name` | Identificador | Acesso restrito ao banco | Exibição nas telas |
| `consentimento_consentimento` (finalidade, versão, datas) | Metadado | Acesso restrito ao banco | Não identifica a pessoa sozinho |
| `usuarios_usuario` (`is_staff`, `is_active`, `date_joined`, `last_login`), `dois_fatores_dispositivototp.ultimo_passo_usado` | Metadado | Acesso restrito ao banco | Controle de acesso, gerado pelo sistema |
| `usuarios_contadordetentativas.chave` | Metadado | Hash SHA-256 do nome e do endereço | Contar tentativas sem guardar quem tentou |
| `logs/seguranca.log` (`username` e evento) | Identificador | HMAC-SHA256 encadeado (integridade, não sigilo) | Precisa ser lido por quem investiga um incidente |

**O que é "acesso restrito ao banco".** O PostgreSQL não publica porta
nenhuma: só o container da aplicação o alcança, pela rede interna do
Docker (`docker-compose.yml`). O usuário do banco e a senha ficam no
`.env` da VPS, fora do repositório. Os dados ficam num volume local da
VPS, e o tráfego entre o navegador e o servidor é TLS 1.3.

**Por que nome, e-mail e username não são cifrados.** A ASVS 4.0.3
(V6.1.1) recomenda cifrar em repouso os dados pessoais regulados, e o
grupo aplicou isso ao RA. Para os demais, a decisão foi aceitar o risco,
pelos motivos abaixo, e não deixar isso implícito:

- **A chave ficaria no mesmo servidor do banco.** A cifragem na aplicação
  protege contra quem obtém só o banco ou uma cópia dele (um dump, um
  volume copiado). Quem controla o servidor lê a chave do `.env` e
  decifra tudo. Contra esse atacante, cifrar mais campos não muda nada.
- **Username e e-mail são buscados pelo valor.** O login procura o
  username exato a cada tentativa, e a gestão busca por parte do nome, do
  username e do e-mail. Cifrar exigiria um índice para cada campo, como
  foi feito com o RA, e a busca por parte do texto deixaria de existir.
- **Nome e e-mail sozinhos identificam menos que o RA.** O RA é o número
  que a Secretaria da Educação usa para o aluno em todos os sistemas
  dela. Por isso ele foi o campo escolhido.

O risco que fica é o de um vazamento do banco expor nome, username e
e-mail. Ele está registrado em `ANALISE_RISCOS.md`. Cifrar o volume do
banco no disco da VPS reduziria esse risco sem mudar a aplicação, mas
depende de configuração do servidor e não foi feito.

## 7. O que decide qual estratégia usar

A regra prática do projeto: se o sistema nunca precisa ler o valor
original de volta, usa hash. Se precisa ler de volta, usa cifragem
reversível com chave protegida. Se o dado precisa continuar legível,
mas sua integridade precisa ser verificável, usa assinatura (HMAC) em
vez de cifragem ou hash. Não existe, hoje, nenhum dado no projeto fora
desses três casos.
