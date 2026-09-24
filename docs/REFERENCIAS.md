# Fontes Técnicas e Científicas (Issue 6.11)

Este documento liga cada decisão de segurança do CirculaGov à fonte que a
sustenta. Não é uma lista de leitura solta: cada entrada diz o que a fonte
afirma, onde isso aparece no código e por que a equipe seguiu ou não seguiu a
recomendação.

Todas as fontes abaixo foram abertas e lidas no trecho citado. A seção 10 traz
um roteiro de leitura para conferir as passagens antes da apresentação.

A normalização das referências em ABNT NBR 6023 é feita na issue 6.12.

---

## 1. Hash de senha: parâmetros do Argon2id

**Fonte:** OWASP. *Password Storage Cheat Sheet*. OWASP Cheat Sheet Series.
Disponível em: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
Acesso em: 24 set. 2026.

**O que diz, textualmente:**

> Use Argon2id with a minimum configuration of 19 MiB of memory, an iteration
> count of 2, and 1 degree of parallelism.

A mesma página apresenta a tabela de configurações aceitáveis, entre elas
`m=19456 (19 MiB), t=2, p=1`.

**Onde foi aplicado:** `usuarios/hashers.py`

```python
class Argon2PasswordHasherCirculaGov(Argon2PasswordHasher):
    time_cost = 2
    memory_cost = 19 * 1024  # 19 MiB, em KiB
    parallelism = 1
```

Os três valores do código correspondem exatamente aos da recomendação:
`19 * 1024 = 19456`.

**Requisitos atendidos:** 1.1 e 1.2.

---

## 2. Hash de senha: a especificação do algoritmo

**Fonte:** BIRYUKOV, A.; DINU, D.; KHOVRATOVICH, D.; JOSEFSSON, S. *Argon2
Memory-Hard Function for Password Hashing and Proof-of-Work Applications*.
RFC 9106. IETF, set. 2021. Categoria: Informational.
Disponível em: https://www.rfc-editor.org/rfc/rfc9106.txt
Acesso em: 24 set. 2026.

**O que diz, textualmente,** sobre qual variante escolher:

> If you do not know the difference between the types or you consider
> side-channel attacks to be a viable threat, choose Argon2id.

**Onde foi aplicado:** a escolha pelo Argon2**id**, e não pelo Argon2i ou
Argon2d, em `usuarios/hashers.py`.

**Divergência assumida:** a seção 4 da RFC recomenda parâmetros bem mais altos
que os da OWASP. A primeira opção é `t=1, p=4, m=2^21` (2 GiB de RAM) e a
segunda é `t=3, p=4, m=2^16` (64 MiB). O projeto usa 19 MiB, que é o mínimo da
OWASP.

A equipe seguiu a OWASP e não a RFC, conscientemente. O motivo está em
[JUSTIFICATIVAS_TECNICAS.md](JUSTIFICATIVAS_TECNICAS.md): o sistema roda em
notebooks comuns durante o desenvolvimento e a apresentação, e 2 GiB de RAM por
tentativa de login inviabilizaria isso. É uma troca de segurança por
viabilidade, e fica registrada como tal em vez de escondida. Em um servidor de
produção, o valor deveria subir.

**Requisito atendido:** 1.2.

---

## 3. Segundo fator: o algoritmo TOTP

**Fonte:** M'RAIHI, D.; MACHANI, S.; PEI, M.; RYDELL, J. *TOTP: Time-Based
One-Time Password Algorithm*. RFC 6238. IETF, maio 2011. Categoria:
Informational.
Disponível em: https://www.rfc-editor.org/rfc/rfc6238.txt
Acesso em: 24 set. 2026.

**O que diz, textualmente:**

> TOTP is the time-based variant of this algorithm, where a value T, derived
> from a time reference and a time step, replaces the counter C in the HOTP
> computation.

Sobre a janela de validação, a seção 5.2 orienta que o validador compare o
código recebido também com marcas de tempo passadas dentro do atraso de
transmissão, e recomenda no máximo um passo de tempo de tolerância.

**Onde foi aplicado:** `dois_fatores/models.py` e `dois_fatores/views.py`, via
biblioteca PyOTP. O projeto usa o comportamento padrão da PyOTP, que segue a
RFC.

**Requisitos atendidos:** 1.5 e 1.6.

---

## 4. Integridade do log: o que é HMAC

**Fonte:** KRAWCZYK, H.; BELLARE, M.; CANETTI, R. *HMAC: Keyed-Hashing for
Message Authentication*. RFC 2104. IETF, fev. 1997.
Disponível em: https://www.rfc-editor.org/rfc/rfc2104.txt
Acesso em: 24 set. 2026.

**O que diz, textualmente:**

> HMAC can be used with any iterative cryptographic hash function, e.g., MD5,
> SHA-1, in combination with a secret shared key.

O mecanismo permite que quem compartilha a chave verifique que a informação não
foi alterada.

**Onde foi aplicado:** `auditoria/integridade.py`

```python
def calcular_mac(chave, mac_anterior, texto):
    mensagem = f'{mac_anterior}{texto}'.encode('utf-8')
    return hmac.new(chave, mensagem, hashlib.sha256).hexdigest()
```

**Por que HMAC e não SHA-256 puro:** é a chave secreta que faz a diferença.
Com hash sem chave, quem edita o arquivo recalcula os hashes e a cadeia volta a
parecer válida. Sem a chave, não.

**Requisito atendido:** 5.3.

---

## 5. Integridade do log: o encadeamento

**Fonte:** SCHNEIER, B.; KELSEY, J. *Secure Audit Logs to Support Computer
Forensics*. ACM Transactions on Information and System Security, v. 2, n. 2,
p. 159-176, maio 1999.
Versão aberta do autor disponível em: https://www.schneier.com/wp-content/uploads/2016/02/paper-auditlogs.pdf
Acesso em: 24 set. 2026.

Este é o artigo científico que embasa a proteção do log. Foi a versão aberta
dos autores que a equipe leu.

**O que diz, textualmente,** no resumo:

> We describe a computationally cheap method for making all log entries
> generated prior to the logging machine's compromise impossible for the
> attacker to read, and also impossible to undetectably modify or destroy.

E na introdução, sobre o objetivo:

> we do not want him to be able to alter or delete log entries made before
> time t in such a way that his manipulation will be undetected

**O mecanismo do artigo:** cada entrada recebe um valor encadeado, na forma
`Yj = H(Y(j-1), EKj(Dj), Wj)`, ou seja, o hash de cada entrada cobre o hash da
entrada anterior. Sobre esse valor é calculado um MAC.

**Onde foi aplicado:** `auditoria/integridade.py`. O CirculaGov usa uma versão
simplificada da mesma ideia: o MAC de cada linha cobre o MAC da linha anterior
mais o texto da linha atual. A parte de cifragem das entradas (`EKj(Dj)`) não
foi implementada, porque o requisito do checklist é detectar alteração, não
impedir leitura.

**O que isso resolve e o que não resolve:** encadear faz com que apagar,
alterar ou reordenar uma linha quebre a verificação. O artigo trata de uma
máquina não confiável que interage periodicamente com uma máquina confiável. O
CirculaGov não tem essa segunda máquina, então um invasor com acesso de escrita
ainda pode apagar o arquivo inteiro. Essa limitação está registrada em
[INTEGRIDADE_LOGS.md](INTEGRIDADE_LOGS.md).

**Requisito atendido:** 5.3.

---

## 6. Criptografia em repouso: AES-GCM

**Fonte:** DWORKIN, M. *Recommendation for Block Cipher Modes of Operation:
Galois/Counter Mode (GCM) and GMAC*. NIST Special Publication 800-38D.
Gaithersburg: National Institute of Standards and Technology, nov. 2007.
Disponível em: https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-38d.pdf
Acesso em: 24 set. 2026.

**O que diz, textualmente,** sobre o nonce:

> The IV is essentially a nonce, i.e, a value that is unique within the
> specified context, which determines an invocation of the authenticated
> encryption function on the input data to be protected.

E sobre o tamanho:

> For IVs, it is recommended that implementations restrict support to the
> length of 96 bits, to promote interoperability, efficiency, and simplicity
> of design.

**Onde foi aplicado:** `dois_fatores/cripto.py`

```python
TAMANHO_NONCE = 12
...
nonce = os.urandom(TAMANHO_NONCE)
```

12 bytes são exatamente os 96 bits recomendados. O nonce é gerado novo a cada
cifragem com `os.urandom`, atendendo ao requisito de unicidade.

**Requisitos atendidos:** 3.4 e 3.5.

---

## 7. Transporte: HSTS

**Fonte:** HODGES, J.; JACKSON, C.; BARTH, A. *HTTP Strict Transport Security
(HSTS)*. RFC 6797. IETF, nov. 2012. Categoria: Standards Track.
Disponível em: https://www.rfc-editor.org/rfc/rfc6797.txt
Acesso em: 24 set. 2026.

**O que diz, textualmente,** no resumo:

> This specification defines a mechanism enabling web sites to declare
> themselves accessible only via secure connections

**Sobre a limitação da primeira visita,** a própria RFC reconhece, na seção
14.6, a vulnerabilidade de bootstrap: quando o usuário digita ou segue um link
com URI `http` para um host HSTS ainda desconhecido, essa primeira conexão
continua exposta a ataque de intermediário.

**Onde foi aplicado:** `config/settings.py`, dentro do bloco `if not DEBUG:`,
com `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS` e
`SECURE_HSTS_PRELOAD`.

É justamente essa limitação da primeira visita que justifica a flag de preload,
conforme já explicado em [JUSTIFICATIVAS_TECNICAS.md](JUSTIFICATIVAS_TECNICAS.md).
A RFC confirma que o problema existe e não é resolvido por ela.

**Requisitos atendidos:** 3.1 e 3.2.

---

## 8. Proteção de dados pessoais

**Fonte:** BRASIL. *Lei nº 13.709, de 14 de agosto de 2018*. Lei Geral de
Proteção de Dados Pessoais (LGPD). Brasília, DF: Presidência da República,
2018.
Disponível em: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm
Acesso em: 24 set. 2026.

**Art. 7º, inciso I**, sobre a base legal usada hoje pelo sistema:

> Art. 7º O tratamento de dados pessoais somente poderá ser realizado nas
> seguintes hipóteses: I - mediante o fornecimento de consentimento pelo
> titular

**Art. 7º, inciso III**, que é a base legal que de fato caberia a um serviço
público:

> III - pela administração pública, para o tratamento e uso compartilhado de
> dados necessários à execução de políticas públicas previstas em leis e
> regulamentos ou respaldadas em contratos, convênios ou instrumentos
> congêneres

**Art. 8º, § 5º**, sobre revogação:

> O consentimento pode ser revogado a qualquer momento mediante manifestação
> expressa do titular, por procedimento gratuito e facilitado

**Art. 18**, sobre os direitos do titular, inclui confirmação da existência de
tratamento (I), acesso aos dados (II), portabilidade (V) e eliminação dos dados
tratados com consentimento (VI).

**Onde foi aplicado:**

| Dispositivo | Implementação |
|---|---|
| Art. 7º, I | `consentimento/models.py`, consentimento por finalidade |
| Art. 8º, § 5º | `consentimento/views.py`, função `revogar` |
| Art. 18, I e II | `direitos_titular/views.py`, função `consultar` |
| Art. 18, V | `direitos_titular/views.py`, função `exportar`, saída em JSON |
| Art. 18, VI | `direitos_titular/views.py`, função `excluir` |

**Ponto a assumir:** o sistema usa consentimento (art. 7º, I) como base legal.
Para um serviço público obrigatório, a base mais adequada seria o art. 7º, III,
porque o aluno não tem liberdade real de recusar e ainda assim usar a
biblioteca da escola. O projeto manteve o consentimento porque o checklist
pede explicitamente registro e revogação de consentimento nos itens 4.4 a 4.7.
Fica registrado como escolha didática, não como recomendação jurídica.

**Requisitos atendidos:** bloco 4 inteiro.

---

## 9. Quadro resumo

| Decisão | Fonte | Requisitos |
|---|---|---|
| Parâmetros do Argon2id | OWASP Password Storage Cheat Sheet | 1.1, 1.2 |
| Escolha do Argon2id | RFC 9106 | 1.2 |
| TOTP no segundo fator | RFC 6238 | 1.5, 1.6 |
| HMAC no log | RFC 2104 | 5.3 |
| Encadeamento do log | Schneier e Kelsey (1999) | 5.3 |
| AES-GCM e nonce de 96 bits | NIST SP 800-38D | 3.4, 3.5 |
| HSTS e preload | RFC 6797 | 3.1, 3.2 |
| Consentimento e direitos do titular | Lei 13.709/2018 | bloco 4 |

---

## 10. Roteiro de leitura

Antes da apresentação, vale abrir cada fonte e conferir a passagem citada. O
professor pode perguntar. A ordem abaixo vai do mais curto para o mais longo.

| Ordem | Fonte | O que ler | Tempo |
|---|---|---|---|
| 1 | OWASP Password Storage | a seção do Argon2id, são poucas linhas | 3 min |
| 2 | RFC 9106 | só a seção 4, Parameter Choice | 5 min |
| 3 | NIST SP 800-38D | a seção 5.2.1.1, sobre o IV de 96 bits | 5 min |
| 4 | RFC 2104 | o resumo e a seção 1 | 5 min |
| 5 | RFC 6238 | o resumo e a seção 5.2 | 8 min |
| 6 | Lei 13.709/2018 | arts. 7º, 8º § 5º e 18 | 10 min |
| 7 | RFC 6797 | o resumo e a seção 14.6 | 10 min |
| 8 | Schneier e Kelsey | o resumo, a introdução e a figura 1 | 20 min |

As três perguntas mais prováveis, e onde está a resposta:

1. **Por que 19 MiB e não os 2 GiB da RFC?** Seção 2 deste documento.
2. **Por que HMAC e não hash simples?** Seção 4 deste documento.
3. **Por que consentimento se o serviço é público?** Seção 8 deste documento.
