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
migrações (inclusive a dos contadores de tentativas), coleta os estáticos e sobe o Gunicorn.

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

## Política de conteúdo (CSP)

O Django envia `Content-Security-Policy` em toda resposta, e o nginx não
precisa de configuração para isso. Para conferir de fora:

```bash
curl -sI https://circulagov.nossoprojeto.app.br/contas/login/ | grep -i content-security
```

Deve aparecer `script-src 'self'` e nenhum `unsafe-inline`. Se uma tela
perder o estilo depois de uma mudança, abra o console do navegador: a causa
mais comum é uma classe do Tailwind nova que não está em
`static/css/tailwind.css`. O teste `TesteCssDoTailwindVersionado` avisa
quando isso acontece, e o CSS precisa ser gerado de novo com as classes
novas.

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

## Limite de requisições no nginx

O contador de força bruta do aplicativo é por nome de usuário. Falta um limite
por endereço na frente dele, que barre quem dispara muitas tentativas com nomes
inventados, e que cubra as telas que não têm trava nenhuma no código: a
verificação do segundo fator e o pedido de recuperação de senha.

A configuração está em `deploy/nginx/` e **só vale depois de instalada no nginx
do servidor**. Este repositório não a aplica sozinho.

| Limite, por IP | Taxa | Burst |
|---|---|---|
| `POST /contas/login/` | 30 por minuto | 15 |
| `POST /dois-fatores/verificar/` | 10 por minuto | 5 |
| `POST /recuperar-senha/` | 3 por minuto | 3 |
| qualquer rota | 20 por segundo | 60 |

Quem passa do limite recebe `429 Too Many Requests`. O burst existe para quem erra a
senha duas vezes seguidas não ser barrado.

### Instalar

```bash
cd ~/apps/circulagov
git pull
sudo cp deploy/nginx/circulagov-limites.conf /etc/nginx/conf.d/
sudo cp deploy/nginx/circulagov-limites-servidor.conf /etc/nginx/snippets/
```

Agora acrescente **uma linha** dentro do bloco `server` que escuta na porta 443,
no arquivo do site. O certbot mexeu nesse arquivo, então abra e confira antes de
editar:

```bash
sudo nano /etc/nginx/sites-available/circulagov
```

A linha:

```nginx
include /etc/nginx/snippets/circulagov-limites-servidor.conf;
```

Ela vai no bloco do `listen 443 ssl`, não no que só redireciona a porta 80.
Depois, **sempre teste antes de recarregar**:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Se o `nginx -t` reclamar, o nginx continua rodando com a configuração antiga.
Não recarregue até ele aprovar.

### Conferir que está valendo

De fora do servidor, com **uma única conexão**:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  "https://circulagov.nossoprojeto.app.br/contas/login/?[1-40]" | sort | uniq -c
```

O esperado é algo como `16 403` e `24 429`. O 403 é a proteção CSRF do Django
respondendo a um POST sem formulário, o que é normal e mostra que a requisição
passou pelo nginx. O que prova o limite são os 429.

**Por que numa conexão só.** O login admite uma requisição a cada 2 segundos, com
folga de 15. Um `curl` por requisição abre uma conexão HTTPS nova a cada vez, e
isso pode levar uns 0,6 segundo cada: 20 requisições somam mais de 10 segundos,
o balde esvazia no mesmo ritmo em que enche, e nenhuma é barrada. Foi o que
aconteceu na primeira conferência, e a configuração estava certa. Se vierem só
403, antes de concluir que o `include` está no bloco errado, confirme que o teste
foi numa conexão só.

Isso limita o seu IP no login por alguns segundos, e passa sozinho.

### Estado em produção

Instalado no nginx do servidor em 03/10/2026 e conferido de fora, pela internet,
numa conexão só:

| Cenário | Passaram | Receberam 429 |
|---|---|---|
| 40 POST em `/contas/login/` | 18 | 22 |
| 12 POST em `/dois-fatores/verificar/` | 6 | 6 |
| 8 POST em `/recuperar-senha/` | 4 | 4 |
| 40 GET em `/contas/login/`, com o limite de POST esgotado | 40 | 0 |

A última linha é a que mostra que o GET não é contado no limite do POST. Os
números do 2FA e da recuperação são os mesmos do teste automatizado.

### Voltar atrás

Apague a linha do `include`, rode `sudo nginx -t && sudo systemctl reload nginx`.

### O teste automatizado

`deploy/nginx/testar-limites.sh` sobe um nginx de verdade num container, com um
servidor falso atrás, e confere que o 429 aparece onde deve e **não** aparece
onde não deve. Por exemplo, que um GET em `/contas/login/` não é contado no
limite do POST. Roda no GitHub Actions a cada push, como o job `nginx`. Precisa
de Docker e de rede `host`, então localmente só em Linux.

### O que este limite não resolve

- **Ataque distribuído.** O limite é por IP. Quem usa muitos endereços passa por
  ele, e a defesa contra isso é outra camada, fora do alcance do projeto.
- **Trava por conta no segundo fator.** O limite reduz a velocidade, mas a
  verificação do 2FA continua sem bloqueio por conta no código. Um atacante que
  já tem a senha pode, de um endereço só, tentar até 14 mil códigos por dia.
- **Cota de e-mail.** Três pedidos por minuto de um único endereço somam mais de
  4 mil por dia, mais que a cota diária de envios de uma conta Gmail. O limite
  contém o abuso, mas não o impede.
- **Endereço compartilhado.** Uma sala inteira atrás do mesmo endereço de rede
  divide o mesmo limite. Se isso virar problema, aumente `rate` e `burst` em
  `circulagov-limites.conf`.
- **Proxy na frente do nginx.** Se um dia o site ficar atrás de um CDN, o nginx
  passa a enxergar o endereço do CDN, e todos dividem o mesmo limite. Será
  preciso o módulo `real_ip`.

## Âncoras do log

A cadeia do log não percebe o corte do final do arquivo. Uma âncora
(`manage.py emitir_ancora`) registra quantas linhas o log tinha e qual era a
assinatura da última, e a verificação passa a reprovar se isso mudar. Detalhes
em `INTEGRIDADE_LOGS.md`.

Para emitir uma âncora e mandá-la para fora do servidor:

```bash
cd ~/apps/circulagov
docker compose exec web python manage.py emitir_ancora --email seu-email@exemplo.com
```

Guarde as mensagens recebidas num único arquivo de texto. Para conferir, copie o
arquivo para dentro do contêiner e rode:

```bash
docker compose cp ancoras.txt web:/tmp/ancoras.txt
docker compose exec web python manage.py verificar_logs --ancoras /tmp/ancoras.txt
```

A frequência define a janela cega: o que for apagado depois da última âncora
não é detectado. Emitir uma por dia, por exemplo com o `cron` do servidor,
reduz essa janela a um dia. Isso ainda não está agendado.

## Se a cadeia do log quebrar

A tela `/auditoria/integridade/` e o comando `verificar_logs` mostram
"Log alterado na linha N". Antes de supor adulteração, olhe o que mudou
no servidor: o defeito de vários workers, já corrigido, produzia exatamente
esse sintoma.

Para guardar o arquivo quebrado e começar uma cadeia nova, sem apagar nada:

```bash
cd ~/apps/circulagov
docker compose exec web sh -c 'mv logs/seguranca.log "logs/seguranca-quebrado-$(date +%Y%m%d-%H%M%S).log"'
docker compose restart web
```

O `restart` é necessário: os processos mantêm o arquivo aberto, e sem ele
continuariam gravando no arquivo renomeado.

Depois, para conferir que a cadeia nova fecha:

```bash
docker compose exec web python manage.py verificar_logs
```

Guarde o arquivo separado. Ele é a única prova do que aconteceu até ali,
mesmo sem integridade verificável.

## Limitações conhecidas

- não há backup automático do banco nem do log, só os volumes locais
- não há rotação do arquivo de log
- o deploy é manual, sem integração contínua
