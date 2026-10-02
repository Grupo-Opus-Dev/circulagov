# Deploy em Produção

Como o CirculaGov sobe numa VPS, o que precisa existir antes, e por que
cada peça está onde está.

## Desenho

```
Internet
   |  443 (TLS) e 80 (validação do certificado)
nginx no host
   |  proxy_pass para 127.0.0.1:8000, enviando X-Forwarded-Proto
Docker
   |-- web    Gunicorn com a aplicação Django
   `-- banco  PostgreSQL 17
```

O nginx roda **no host**, não em container. Assim o certbot do sistema cuida
da renovação do certificado sozinho, e uma falha no deploy da aplicação não
derruba o proxy junto.

O container da aplicação publica a porta **amarrada em `127.0.0.1`**. Isso não
é detalhe de estilo: o Docker escreve as próprias regras de iptables e passa
por cima do UFW. Publicada como `"8000:8000"`, a porta ficaria exposta na
internet mesmo com o firewall dizendo que está fechada.

## Volumes, e por que eles importam

| Volume | Conteúdo | O que acontece sem ele |
|---|---|---|
| `dados_postgres` | banco | todo rebuild apaga usuários, consentimentos e tokens |
| `logs_seguranca` | `logs/seguranca.log` | a cadeia de HMAC recomeça do zero **em silêncio**, destruindo a auditoria do requisito 5.3 |

O segundo é o mais traiçoeiro: o `HandlerLogIntegro` retoma a cadeia lendo o
último MAC do arquivo. Se o arquivo não existe, ele começa de novo sem erro
nenhum, e ninguém percebe que o histórico anterior sumiu.

## Pré-requisitos

**Na VPS:** Ubuntu endurecido conforme o procedimento de setup, com Docker,
Docker Compose, UFW liberando 22, 80 e 443, e acesso só por chave SSH.

**No DNS:** registro A do subdomínio apontando para o IP da VPS.

**nginx e certbot** instalados no host.

## Passo a passo

### 1. Clonar

```bash
cd ~/apps
git clone https://github.com/Grupo-Opus-Dev/circulagov.git
cd circulagov
```

### 2. Criar o `.env` de produção

```bash
cp .env.example .env
nano .env
```

Preencha, no mínimo:

- `DEBUG=False`
- `SECRET_KEY`, `CHAVE_CIFRAGEM_2FA` e `CHAVE_INTEGRIDADE_LOGS` com valores
  **novos**, gerados na VPS, diferentes dos de desenvolvimento
- `DB_PASSWORD` com uma senha nova
- `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` com o domínio real
- as variáveis de e-mail, se a recuperação de senha for operar

Para gerar as chaves:

```bash
python3 -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"
```

As chaves de produção precisam ser diferentes das de desenvolvimento. Se forem
iguais, qualquer pessoa com o `.env` local consegue forjar linha de log
assinada em produção.

### 3. Subir

```bash
docker compose up -d --build
docker compose logs -f web
```

O `entrypoint.sh` roda sozinho a cada subida: espera o banco, aplica
migrações, cria a tabela de cache, coleta os estáticos e sobe o Gunicorn.

### 4. Criar o administrador

```bash
docker compose exec web python manage.py createsuperuser
```

### 5. Configurar o nginx

O bloco mínimo, antes do certificado existir:

```nginx
server {
    listen 80;
    server_name circulagov.nossoprojeto.app.br;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

A última linha é a crítica. Sem ela, o Django recebe a requisição como HTTP,
o `SECURE_SSL_REDIRECT` manda para HTTPS, o nginx devolve como HTTP de novo, e
o site entra em laço infinito de redirecionamento.

### 6. Emitir o certificado

```bash
sudo certbot --nginx -d circulagov.nossoprojeto.app.br
```

O certbot ajusta o nginx e instala um timer de renovação automática.

A **porta 80 precisa ficar aberta permanentemente**. É por ela que o Let's
Encrypt valida o domínio. Fechar depois quebra a renovação, e o certificado
vence em 90 dias.

## Atualizar depois de um merge na main

```bash
cd ~/apps/circulagov
git pull
docker compose up -d --build
```

Os volumes não são tocados. Migrações novas são aplicadas pelo entrypoint.

## Voltar atrás

```bash
git checkout v1.4.0-m6
docker compose up -d --build
```

Cuidado: isso reverte o código, não o banco. Migração que apagou coluna não
volta sozinha.

## Verificação

```bash
docker compose ps
docker compose exec web python manage.py verificar_logs
curl -I https://circulagov.nossoprojeto.app.br
```

E, de fora da VPS, confirme que só 22, 80 e 443 respondem. A 8000 precisa
estar inacessível: se responder, a porta foi publicada sem o `127.0.0.1`.

## Limitações conhecidas

- não há backup automático do banco nem do log, só os volumes locais
- não há rotação do arquivo de log
- o deploy é manual, sem integração contínua
