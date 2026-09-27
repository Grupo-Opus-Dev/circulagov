# Gestão de Credenciais (Issue 6.4)

Este documento reúne, num só lugar, como o CirculaGov trata cada
credencial do sistema: como ela nasce, como é guardada, como é usada e
como morre. As justificativas de cada escolha (o "porquê") continuam em
[`JUSTIFICATIVAS_TECNICAS.md`](JUSTIFICATIVAS_TECNICAS.md), e o passo a
passo de cada fluxo em [`FLUXO_AUTENTICACAO.md`](FLUXO_AUTENTICACAO.md)
e [`FLUXO_RECUPERACAO_SENHA.md`](FLUXO_RECUPERACAO_SENHA.md); aqui o
foco é reunir os dados de cada credencial, sem repetir o fluxo inteiro.

## 1. Senha do usuário

**Nasce:** no cadastro ou na redefinição de senha (fluxo de recuperação
ou troca manual), sempre validada pelos critérios listados em
`AUTH_PASSWORD_VALIDATORS` (`config/settings.py`):

- `UserAttributeSimilarityValidator`: recusa senha parecida demais com
  o nome de usuário ou outros dados do próprio usuário.
- `MinimumLengthValidator`: exige o mínimo padrão do Django, 8
  caracteres.
- `CommonPasswordValidator`: recusa senhas muito comuns (lista padrão
  do Django).
- `NumericPasswordValidator`: recusa senha composta só de números.

**Guardada:** como hash Argon2id, calculado por
`Argon2PasswordHasherCirculaGov` (`usuarios/hashers.py`), com
`time_cost=2`, `memory_cost=19*1024` KiB (19 MiB) e `parallelism=1`,
valores recomendados pelo OWASP Password Storage Cheat Sheet (2024).

**Salt:** cada senha recebe um salt novo, gerado pelo próprio Django
(`BasePasswordHasher.salt`) com um CSPRNG e pelo menos 128 bits de
entropia. Não existe uma coluna separada para o salt: ele fica embutido
no mesmo campo `usuarios_usuario.password`, dentro da string
codificada, no formato
`argon2$argon2id$v=19$m=19456,t=2,p=1$<salt em base64>$<hash em base64>`.

Os hashers antigos (`PBKDF2PasswordHasher`, `PBKDF2SHA1PasswordHasher`)
continuam listados em `PASSWORD_HASHERS` só para conseguir **ler**
hashes antigos; todo hash novo usa Argon2id.

**Usada:** a cada login, o Django decodifica o hash salvo e recalcula o
Argon2id sobre a senha digitada, usando o mesmo salt e os mesmos
parâmetros armazenados na própria string codificada.

**Morre:** nunca expira sozinha. É substituída quando o usuário troca
de senha (fluxo de recuperação, `set_password` em
`recuperacao_senha/views.py`) ou desaparece junto com a conta, se o
titular exercer o direito de exclusão (`direitos_titular/views.py`).

## 2. Token de recuperação de senha

**Nasce:** gerado pelo servidor, nunca pelo usuário, em
`TokenRecuperacaoSenha.gerar` (`recuperacao_senha/models.py`), com
`secrets.token_urlsafe(32)` (CSPRNG do sistema operacional).

**Guardada:** só o hash SHA-256 do valor bruto vai para o banco, no
campo `token_hash` (`recuperacao_senha_tokenrecuperacaosenha.token_hash`).
O valor bruto em si só existe na memória da requisição que o gerou, e é
o que vai no link enviado por e-mail.

**Usada:** `TokenRecuperacaoSenha.buscar_com_motivo` recalcula o hash do
valor recebido na URL e compara com o que está salvo, sem nunca
reconstruir o valor original a partir do hash.

**Morre:** o registro expira em 30 minutos (`MINUTOS_VALIDADE_TOKEN`,
contados a partir de `criado_em`) ou fica inválido assim que é usado
uma vez (`marcar_usado`, que preenche `usado_em`), o que ocorrer
primeiro. Não há limpeza automática: o registro continua na tabela
depois de expirado ou usado, só deixa de validar.

## 3. Segredo do 2FA (TOTP)

**Nasce:** gerado pelo servidor com `pyotp.random_base32()`, na primeira
vez que um `DispositivoTOTP` é salvo (`dois_fatores/models.py`), seja no
cadastro do 2FA.

**Guardada:** cifrado com AES-GCM (256 bits) antes de tocar o banco,
pela função `cripto.cifrar` (`dois_fatores/cripto.py`), no campo
binário `segredo_cifrado`. O valor em texto puro nunca é salvo em
lugar nenhum, existe só na memória durante a chamada que o gera.

**Usada:** a cada verificação de código (no cadastro do 2FA e em cada
login), o servidor decifra o segredo na memória
(`DispositivoTOTP.segredo`) só para gerar o código TOTP esperado
naquele instante e comparar com o que o usuário digitou.

**Morre:** enquanto o `DispositivoTOTP` existir, o segredo não muda nem
expira sozinho. É apagado junto com o `Usuario`, por
`on_delete=models.CASCADE`, se o titular excluir a própria conta. Hoje
não existe uma tela para desativar o 2FA sem excluir a conta.

## 4. Onde vivem as chaves

Todas as chaves usadas para cifrar ou assinar dados no CirculaGov ficam
em variáveis de ambiente, no arquivo `.env` (fora do controle de
versão, listado em `.gitignore`), nunca no código-fonte:

| Chave | Variável de ambiente | Protege |
|---|---|---|
| Chave secreta do Django | `SECRET_KEY` | Assinaturas internas do próprio framework (sessões assinadas, tokens do Django) |
| Chave de cifragem do 2FA | `CHAVE_CIFRAGEM_2FA` | Segredo TOTP em repouso (AES-GCM, 256 bits) |
| Chave de integridade dos logs | `CHAVE_INTEGRIDADE_LOGS` | Assinatura HMAC-SHA256 encadeada do log de segurança |

Cada chave tem uma única finalidade: se uma vazar, as outras proteções
continuam valendo. Mais detalhes de cada uma em
[`ESTRATEGIA_CRIPTOGRAFIA.md`](ESTRATEGIA_CRIPTOGRAFIA.md).

## 5. Expiração de sessão

**Nasce:** no momento em que `login()` do Django é chamado (com ou sem
2FA), o sinal `user_logged_in` dispara `gravar_inicio_da_sessao`
(`usuarios/signals.py`), que grava o horário do início na própria
sessão.

**Guardada:** na tabela `django_session`, o backend de sessão padrão do
Django (baseado em banco de dados), já que o projeto não sobrescreve
`SESSION_ENGINE`.

**Usada:** a cada requisição de um usuário autenticado,
`TimeoutAbsolutoMiddleware` (`usuarios/middleware.py`) confere se o
tempo desde o início da sessão já passou do limite.

**Morre**, por qualquer um destes motivos, o que ocorrer primeiro:

- **Inatividade:** `SESSION_COOKIE_AGE` = 30 minutos, renovado a cada
  requisição (`SESSION_SAVE_EVERY_REQUEST=True`).
- **Tempo absoluto:** `TEMPO_MAXIMO_SESSAO_SEGUNDOS` = 12 horas desde o
  login, mesmo que o usuário continue ativo o tempo todo.
- **Logout:** remove a linha correspondente da tabela `django_session`
  no servidor, então um cookie antigo reaproveitado depois não
  autentica mais.
- **Falta da marca de início:** se por qualquer motivo a sessão não tem
  o horário de início gravado, o middleware trata como expirada
  (comportamento fail-closed), em vez de assumir que não tem limite.

Não há uma rotina automática que apague linhas expiradas da tabela
`django_session`; elas só deixam de autenticar, mas continuam ocupando
espaço até uma limpeza manual (`clearsessions`, comando nativo do
Django, ainda não agendado neste projeto).
