#!/usr/bin/env bash
#
# Testa os limites de requisicoes com um nginx de verdade, num container,
# e um servidor falso atras dele. Confere que o 429 aparece onde deve e
# NAO aparece onde nao deve.
#
# Precisa de Docker e de rede "host", entao roda em Linux. No GitHub
# Actions roda a cada push. Uso: bash deploy/nginx/testar-limites.sh

set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
IMAGEM="${IMAGEM_NGINX:-nginx:1.24-alpine}"
NOME="circulagov-nginx-teste"
URL="http://127.0.0.1:8081"
FALHAS=0

limpar() {
    docker rm -f "$NOME" >/dev/null 2>&1 || true
    [ -n "${PID_FALSO:-}" ] && kill "$PID_FALSO" >/dev/null 2>&1 || true
}
trap limpar EXIT

ok()    { printf '  [ok]    %s\n' "$1"; }
falha() { printf '  [FALHA] %s\n' "$1"; FALHAS=$((FALHAS + 1)); }

rodar_nginx() {
    docker run --rm --network host \
        -v "$AQUI/teste/nginx.conf:/etc/nginx/nginx.conf:ro" \
        -v "$AQUI/circulagov-limites.conf:/etc/nginx/conf.d/circulagov-limites.conf:ro" \
        -v "$AQUI/circulagov-limites-servidor.conf:/etc/nginx/snippets/circulagov-limites-servidor.conf:ro" \
        "$@"
}

# Manda N requisicoes em sequencia e imprime os codigos de resposta.
disparar() {
    local metodo="$1" caminho="$2" quantidade="$3"
    for _ in $(seq 1 "$quantidade"); do
        curl -s -o /dev/null -w '%{http_code}\n' -X "$metodo" "$URL$caminho"
    done
}

# Conta quantas respostas foram 429.
rejeitadas() { grep -c '^429$' || true; }

# O teto geral (burst 60) tambem conta estas requisicoes. Cada secao manda
# menos que isso, e a pausa deixa o balde encher de novo antes da proxima.
pausar() { sleep 4; }

echo "== 1. Sintaxe da configuracao =="
if rodar_nginx "$IMAGEM" nginx -t 2>&1 | tail -2; then
    ok "nginx -t aceitou a configuracao"
else
    falha "nginx -t recusou a configuracao"
    exit 1
fi

echo "== 2. Subindo o nginx e o servidor falso =="
python3 - <<'PY' &
import http.server

class Falso(http.server.BaseHTTPRequestHandler):
    def _responder(self):
        self.send_response(200)
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'ok')
    do_GET = do_POST = _responder
    def log_message(self, *args):
        pass

http.server.ThreadingHTTPServer(('127.0.0.1', 9000), Falso).serve_forever()
PY
PID_FALSO=$!

rodar_nginx -d --name "$NOME" "$IMAGEM" >/dev/null
for _ in $(seq 1 30); do
    curl -s -o /dev/null "$URL/" && break
    sleep 0.5
done
curl -s -o /dev/null "$URL/" && ok "nginx respondendo" || { falha "nginx nao subiu"; exit 1; }
pausar

echo "== 3. Login: o POST e limitado, o GET nao =="
# 40 GET passam do burst do login (15), mas nao devem ser contados nele.
r=$(disparar GET /contas/login/ 40 | rejeitadas)
[ "$r" -eq 0 ] && ok "40 GET em /contas/login/: nenhum 429" \
                || falha "GET em /contas/login/ foi limitado ($r respostas 429)"
pausar
saida=$(disparar POST /contas/login/ 20)
r=$(echo "$saida" | rejeitadas)
primeiras=$(echo "$saida" | head -5 | rejeitadas)
[ "$r" -ge 2 ] && ok "20 POST seguidos: $r receberam 429" \
                || falha "POST em /contas/login/ nao foi limitado ($r respostas 429)"
[ "$primeiras" -eq 0 ] && ok "as 5 primeiras tentativas passaram, quem erra a senha uma ou duas vezes nao e barrado" \
                        || falha "as primeiras tentativas ja foram barradas"
pausar

echo "== 4. Segundo fator =="
r=$(disparar POST /dois-fatores/verificar/ 12 | rejeitadas)
[ "$r" -ge 2 ] && ok "12 POST seguidos: $r receberam 429" \
                || falha "POST em /dois-fatores/verificar/ nao foi limitado ($r respostas 429)"
pausar

echo "== 5. Recuperacao de senha =="
r=$(disparar POST /recuperar-senha/ 8 | rejeitadas)
[ "$r" -ge 2 ] && ok "8 POST seguidos: $r receberam 429" \
                || falha "POST em /recuperar-senha/ nao foi limitado ($r respostas 429)"
# A tela de pedir recuperacao (GET) precisa continuar abrindo.
c=$(curl -s -o /dev/null -w '%{http_code}' "$URL/recuperar-senha/")
[ "$c" = "200" ] && ok "GET em /recuperar-senha/ continua abrindo" \
                  || falha "GET em /recuperar-senha/ devolveu $c"
pausar

echo "== 6. Rotas que nao tem limite proprio =="
c=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$URL/consentimento/revogar/1/")
[ "$c" = "200" ] && ok "um POST comum passa" || falha "um POST comum devolveu $c"

echo "== 7. Teto geral por IP =="
saida=$(curl -s -o /dev/null -w '%{http_code}\n' "$URL/geral/?[1-250]")
r=$(echo "$saida" | rejeitadas)
primeiras=$(echo "$saida" | head -40 | rejeitadas)
[ "$r" -ge 50 ] && ok "250 requisicoes de uma vez: $r receberam 429" \
                 || falha "o teto geral nao barrou a inundacao ($r respostas 429)"
[ "$primeiras" -eq 0 ] && ok "as primeiras 40 passaram, o burst absorve navegacao normal" \
                        || falha "as primeiras requisicoes ja foram barradas"

echo
if [ "$FALHAS" -eq 0 ]; then
    echo "Todos os testes dos limites passaram."
else
    echo "$FALHAS verificacao(oes) falharam."
    exit 1
fi
