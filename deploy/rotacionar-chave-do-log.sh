#!/usr/bin/env bash
#
# Rotação da chave do log de segurança (requisito 5.3).
#
# Rodar na VPS, na pasta do projeto:  ./deploy/rotacionar-chave-do-log.sh
# Opcional: ANCORA_EMAIL=alguem@exemplo.com para receber a âncora de
# fechamento do log antigo por e-mail.
#
# O que faz, em ordem:
#  1. para o container web, para nada ser gravado durante a troca;
#  2. confere o log com a chave atual, emite uma âncora de fechamento e
#     renomeia seguranca.log e ancoras.log com a data (arquivar_log);
#  3. guarda a chave antiga fora do projeto, só legível pelo dono, porque
#     ela é necessária para auditar o log arquivado;
#  4. troca CHAVE_INTEGRIDADE_LOGS no .env por uma chave nova;
#  5. sobe o web de novo, que começa uma cadeia nova com a chave nova.
#
# Se o passo 2 falhar (log adulterado), nada muda e o web volta a subir.

set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    echo "Arquivo .env não encontrado em $(pwd)." >&2
    exit 1
fi
if ! grep -q '^CHAVE_INTEGRIDADE_LOGS=' .env; then
    echo "CHAVE_INTEGRIDADE_LOGS não está no .env." >&2
    exit 1
fi

PASTA_CHAVES="${PASTA_CHAVES_ANTIGAS:-$HOME/circulagov-chaves-antigas}"
CARIMBO="$(date -u +%Y%m%d-%H%M%S)"

EMAIL_ARGS=()
if [ -n "${ANCORA_EMAIL:-}" ]; then
    EMAIL_ARGS=(--email "$ANCORA_EMAIL")
fi

echo "[rotacao] parando o web"
docker compose stop web

# Se algo der errado daqui em diante, o web volta com a chave que estiver
# no .env naquele momento.
trap 'echo "[rotacao] falhou, subindo o web de novo"; docker compose up -d web' ERR

echo "[rotacao] arquivando o log com a chave atual"
docker compose run --rm --no-deps -T --entrypoint python web \
    manage.py arquivar_log --carimbo "$CARIMBO" "${EMAIL_ARGS[@]}"

echo "[rotacao] guardando a chave antiga em $PASTA_CHAVES"
umask 077
mkdir -p "$PASTA_CHAVES"
grep '^CHAVE_INTEGRIDADE_LOGS=' .env | cut -d= -f2- \
    > "$PASTA_CHAVES/chave-log-$CARIMBO.txt"

echo "[rotacao] gerando a chave nova no .env"
NOVA="$(python3 -c 'import base64, os; print(base64.b64encode(os.urandom(32)).decode())')"
# Base64 não tem "#", por isso ele serve de separador no sed.
sed -i "s#^CHAVE_INTEGRIDADE_LOGS=.*#CHAVE_INTEGRIDADE_LOGS=$NOVA#" .env
unset NOVA

trap - ERR
echo "[rotacao] subindo o web com a chave nova"
docker compose up -d --force-recreate web

cat <<FIM

Rotação concluída. Arquivos no volume de logs:
  logs/seguranca-$CARIMBO.log
  logs/ancoras-$CARIMBO.log
Chave antiga: $PASTA_CHAVES/chave-log-$CARIMBO.txt

Para auditar o log arquivado (a chave entra pela entrada padrão):
  docker compose exec -T web python manage.py verificar_logs \
      --arquivo logs/seguranca-$CARIMBO.log \
      --ancoras logs/ancoras-$CARIMBO.log --chave-arquivo - \
      < $PASTA_CHAVES/chave-log-$CARIMBO.txt
FIM
