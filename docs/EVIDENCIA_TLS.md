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
commitado (está no `.gitignore`) — em produção, o certificado seria
emitido por uma autoridade certificadora de verdade (ex: Let's Encrypt),
atrás de um proxy como Nginx.

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
