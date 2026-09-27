# Estratégia de Criptografia (Issue 3.7)

Este documento resume onde e como o CirculaGov usa criptografia hoje,
separando dado em trânsito de dado em repouso. As justificativas de
cada escolha estão em [`JUSTIFICATIVAS_TECNICAS.md`](JUSTIFICATIVAS_TECNICAS.md).

## Tabela resumo

| Dado protegido | Algoritmo | Onde no código | Chave usada |
|---|---|---|---|
| Senha do usuário | Argon2id | `usuarios/hashers.py` | Não aplicável, hash de mão única, sem chave |
| Segredo do 2FA (TOTP) em repouso | AES-GCM (256 bits) | `dois_fatores/cripto.py` | `CHAVE_CIFRAGEM_2FA` (variável de ambiente, `.env`) |
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

Três estratégias diferentes, dependendo do que o sistema precisa fazer
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

**Assinatura encadeada, com chave (log de segurança):** dado que
precisa ser lido em texto puro (é um log, alguém precisa poder ler as
linhas), mas cuja integridade precisa ser verificável depois. Não é
hash nem cifragem, é assinatura: o texto continua legível, e o
HMAC-SHA256 ao final de cada linha só serve pra provar que ela não foi
alterada desde que foi gravada.

## 7. O que decide qual estratégia usar

A regra prática do projeto: se o sistema nunca precisa ler o valor
original de volta, usa hash. Se precisa ler de volta, usa cifragem
reversível com chave protegida. Se o dado precisa continuar legível,
mas sua integridade precisa ser verificável, usa assinatura (HMAC) em
vez de cifragem ou hash. Não existe, hoje, nenhum dado no projeto fora
desses três casos.
