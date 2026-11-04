# Como reproduzir os resultados

Este documento reúne os comandos para conferir, de forma independente, os
números que o projeto afirma: a quantidade de testes aprovados e a conexão
TLS 1.3 em produção. Cada seção diz o ambiente, o comando, a saída esperada e
o limite do que ela prova.

## 1. Testes automatizados

### Execuções registradas no GitHub Actions

As execuções do CI ficam públicas, com data, commit, versões e log completo.

| Versão | Commit | Resultado | Execução |
|---|---|---|---|
| v1.5.1 (avaliada) | `699a3b3` | `Ran 259 tests in 25.168s`, `OK` | [39148489567](https://github.com/Grupo-Opus-Dev/circulagov/actions/runs/39148489567) |
| `main` depois do PR #117 | `1607149` | `Ran 263 tests in 28.609s`, `OK` | [41846776603](https://github.com/Grupo-Opus-Dev/circulagov/actions/runs/41846776603) |

Os 4 testes a mais da `main` são os do byte nulo na recuperação de senha e na
busca da gestão, trazidos pelo PR #117.

Ambiente das execuções acima, conforme o próprio log:

- Ubuntu 24.04 (runner do GitHub);
- CPython 3.13.16 na v1.5.1 e 3.13.17 na `main`;
- Django 5.2.17 e as demais dependências fixadas em `requirements.txt`;
- PostgreSQL 17 (imagem oficial `postgres:17`), descartável, criado para a execução;
- chaves de criptografia geradas na hora, só para o teste.

No log, procure as linhas `Found 259 test(s).` e `Ran 259 tests`, no passo
"Rodar os testes" do job `testes`.

### Rodando na própria máquina

Requisitos: Python 3.13 e um PostgreSQL 17 acessível.

```bash
git clone https://github.com/Grupo-Opus-Dev/circulagov.git
cd circulagov
git checkout v1.5.1
python -m venv venv
source venv/bin/activate      # no Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copie `.env.example` para `.env`, preencha os dados do banco e gere as chaves
(cada uma diferente):

```bash
python -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"
```

```bash
python manage.py test --no-input
```

Saída esperada no fim:

```
Ran 259 tests in ...s

OK
```

Na `main` atual, o número é 263. O tempo varia com a máquina.

### O que os testes provam e o que não provam

Os testes conferem o comportamento do código: que a senha sozinha não
autentica quem tem 2FA, que o log adulterado é detectado, que o mesmo token
de recuperação não serve duas vezes em pedidos simultâneos, entre outros. A
lista de ameaça e teste está em [TESTES_SEGURANCA.md](TESTES_SEGURANCA.md).

Eles não testam a infraestrutura publicada (nginx, certificado, firewall).
Isso é o que a seção 2 cobre.

## 2. TLS e cabeçalhos em produção

O sistema está no ar em `https://circulagov.nossoprojeto.app.br`, e os
comandos abaixo funcionam de qualquer máquina com OpenSSL e curl.

```bash
# protocolo e cifra negociados
openssl s_client -connect circulagov.nossoprojeto.app.br:443 \
  -servername circulagov.nossoprojeto.app.br </dev/null

# versões antigas devem ser recusadas
openssl s_client -connect circulagov.nossoprojeto.app.br:443 \
  -servername circulagov.nossoprojeto.app.br -tls1_1 </dev/null

# HTTP deve redirecionar para HTTPS (301)
curl -sI http://circulagov.nossoprojeto.app.br/contas/login/

# cabeçalhos de segurança (HSTS, CSP e outros)
curl -sI https://circulagov.nossoprojeto.app.br/contas/login/

# o admin do Django deve mandar para o login da aplicação, que tem o 2FA
curl -sI https://circulagov.nossoprojeto.app.br/admin/login/
```

Saídas esperadas, conforme a captura de 04/11/2026 em
[evidencias/17-evidencia-tls-producao-2026-11-04.txt](evidencias/17-evidencia-tls-producao-2026-11-04.txt):

| Verificação | Esperado |
|---|---|
| Protocolo e cifra | `TLSv1.3`, `TLS_AES_256_GCM_SHA384`, `Verify return code: 0 (ok)` |
| TLS 1.0 e 1.1 | handshake falha |
| HTTP | `301 Moved Permanently` para `https://` |
| HSTS | `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload` |
| CSP | `Content-Security-Policy` com `script-src 'self'`, sem `unsafe-inline` |
| Admin | `302` para `/contas/login/?next=/admin/` |

TLS 1.2 também é aceito, para compatibilidade, com cifra AEAD e troca de chave
efêmera. Um navegador ou cliente atual negocia TLS 1.3.

### Limites

- O TLS termina no nginx. Do nginx até a aplicação o tráfego passa pela
  interface local da própria máquina (`127.0.0.1`), sem sair dela.
- O domínio não está na lista de HSTS preload dos navegadores. Ver
  [EVIDENCIA_TLS.md](EVIDENCIA_TLS.md).
- O certificado atual vale até 31/12/2026 e é renovado automaticamente pelo
  certbot. Uma captura feita depois dessa data mostra datas diferentes.
