# Evidência de Tráfego Cifrado (Issue 3.3)

Este documento comprova que a comunicação HTTPS configurada no projeto
(`config/settings.py`, requisitos 3.1 e 3.2) funciona de verdade, não só
no papel.

## Como foi testado

O servidor de desenvolvimento do Django não fala HTTPS sozinho, então
para gerar essa evidência localmente usamos o `runserver_plus`, do
pacote `django-extensions`, que sobe um servidor com um certificado
autoassinado:

```bash
python manage.py runserver_plus --cert-file dev-cert.crt 127.0.0.1:8443
```

O certificado (`dev-cert.crt`/`dev-cert.key`) é gerado na hora e nunca é
commitado (está no `.gitignore`). Esta é a evidência de **desenvolvimento**.
A de produção, com certificado emitido por uma autoridade certificadora de
verdade, está na seção [Em produção](#em-produção), mais abaixo.

## Resultado

Arquivo completo em [`evidencias/10-evidencia-tls.txt`](evidencias/10-evidencia-tls.txt).
Pontos principais:

**Protocolo e cifra**, obtidos com `openssl s_client`:

```
Protocol  : TLSv1.3
Cipher    : TLS_AES_256_GCM_SHA384
```

TLS 1.3 é a versão mais recente do protocolo, e `AES_256_GCM` é uma
cifra autenticada considerada forte hoje.

**Cabeçalhos de segurança**, obtidos com `curl -v` na mesma conexão:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
Set-Cookie: csrftoken=...; Secure
```

O cabeçalho `Strict-Transport-Security` confirma que o HSTS configurado
no requisito 3.1 está ativo de verdade na resposta. O `Secure` no
cookie confirma o requisito 3.2: esse cookie só é enviado pelo
navegador em conexões HTTPS, nunca em HTTP puro.

## Em produção

O sistema está no ar em `https://circulagov.nossoprojeto.app.br`, atrás de
um nginx, com certificado do Let's Encrypt emitido pelo certbot. A captura
abaixo foi feita de fora da máquina, pela internet pública, em 03/10/2026.
Arquivo completo em
[`evidencias/16-evidencia-tls-producao.txt`](evidencias/16-evidencia-tls-producao.txt).

**Protocolo, cifra e certificado**, obtidos com `openssl s_client`:

```
Protocol  : TLSv1.3
Cipher    : TLS_AES_256_GCM_SHA384
subject=CN=circulagov.nossoprojeto.app.br
issuer=C=US, O=Let's Encrypt, CN=YE2
Verify return code: 0 (ok)
```

O `Verify return code: 0` é o que diferencia esta evidência da local: o
certificado foi validado contra as autoridades confiáveis do sistema, sem
precisar aceitar uma exceção como no certificado autoassinado.

**Validade.** O certificado vale de 02/10/2026 a 31/12/2026, e o certbot
instala um temporizador que renova antes do vencimento.

**Requisito 3.2, bloqueio de conexão insegura.** Uma requisição `http://`
recebe `301 Moved Permanently` com `Location: https://...`, em vez de ser
atendida em texto puro.

**Cabeçalhos de segurança** na resposta HTTPS:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: same-origin
Cross-Origin-Opener-Policy: same-origin
```

### O que esta evidência não cobre

- **HSTS preload.** O cabeçalho declara `preload`, mas o domínio, um
  `.app.br`, **não está na lista de preload dos navegadores**: ao contrário do
  TLD `.app`, o `.br` não vem pré-cadastrado, e o cadastro em hstspreload.org
  é um passo manual que não foi feito. A proteção da primeira visita, antes
  de o navegador ter visto o cabeçalho, não existe. Conferido em 03/10/2026
  na lista estática do Chromium (`transport_security_state_static.json`):
  os TLDs `app` e `dev` constam, e `br`, `app.br` e este domínio não.
- **Rede entre o nginx e o Gunicorn.** O TLS termina no nginx. Dali até a
  aplicação o tráfego passa em texto puro, mas pela interface local
  (`127.0.0.1`) da própria máquina, sem sair dela.
