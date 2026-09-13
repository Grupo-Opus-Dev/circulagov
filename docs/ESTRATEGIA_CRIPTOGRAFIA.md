# Estratégia de Criptografia (Issue 3.7)

Este documento resume onde e como o CirculaGov usa criptografia hoje,
separando dado em trânsito de dado em repouso. As justificativas de
cada escolha estão em [`JUSTIFICATIVAS_TECNICAS.md`](JUSTIFICATIVAS_TECNICAS.md).

## Visão geral

| O quê | Onde | Algoritmo | Chave fica em |
|---|---|---|---|
| Senha do usuário | `usuarios/hashers.py` | Argon2id | Não aplicável (hash, não é reversível) |
| Segredo do 2FA (TOTP) | `dois_fatores/cripto.py` | AES-GCM (256 bits) | `.env`, variável `CHAVE_CIFRAGEM_2FA` |
| Token de recuperação de senha | `recuperacao_senha/models.py` | SHA-256 (hash) | Não aplicável (hash, não é reversível) |
| Tráfego entre navegador e servidor | `config/settings.py` | TLS 1.3 | Certificado do servidor (fora do repositório) |

## 1. Dado em trânsito (rede)

Toda comunicação entre o navegador e o servidor é protegida por
TLS/HTTPS. Em produção (`DEBUG=False`):

- `SECURE_SSL_REDIRECT` redireciona qualquer requisição HTTP pra HTTPS.
- `SESSION_COOKIE_SECURE` e `CSRF_COOKIE_SECURE` impedem que os cookies
  de sessão e CSRF trafeguem fora de uma conexão cifrada.
- `SECURE_HSTS_SECONDS` avisa o navegador pra nunca mais tentar HTTP
  nesse domínio, nem que o usuário digite a URL errada.

Evidência de que isso funciona na prática está em
[`EVIDENCIA_TLS.md`](EVIDENCIA_TLS.md).

## 2. Dado em repouso (banco de dados)

Duas estratégias diferentes, dependendo se o dado precisa ser lido de
volta:

**Hash (senha e token de recuperação):** dado que só precisa ser
*conferido*, nunca lido de volta em texto puro. Usa Argon2id (senha) ou
SHA-256 (token) — funções de mão única, sem chave, sem como reverter.

**Cifragem reversível (segredo do 2FA):** dado que o próprio sistema
precisa ler de volta pra gerar o código TOTP e comparar com o que o
usuário digita, então precisa de uma cifra reversível com chave: AES-GCM.
A chave fica fora do banco e fora do código-fonte, na variável de
ambiente `CHAVE_CIFRAGEM_2FA` (mesmo padrão já usado pra `SECRET_KEY` e
pra senha do PostgreSQL).

## 3. O que decide qual estratégia usar

A regra prática do projeto: se o sistema nunca precisa ler o valor
original de volta, usa hash. Se precisa, usa cifragem reversível com
chave protegida. Não existe um caso no projeto hoje que precise de
cifragem reversível sem essa necessidade de leitura de volta.
