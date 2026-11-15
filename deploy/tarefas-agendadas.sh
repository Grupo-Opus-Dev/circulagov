#!/usr/bin/env bash
#
# Tarefas agendadas do CirculaGov, chamadas pelo cron da VPS
# (deploy/cron/circulagov.cron). Também podem ser rodadas à mão.
#
# Uso: deploy/tarefas-agendadas.sh ancora|expurgo
#
#   ancora   emite uma âncora do log e envia para os endereços em
#            ANCORA_EMAIL no .env (separados por vírgula). É o que tira a
#            âncora do servidor (requisito 5.3).
#   expurgo  apaga tokens de recuperação e contadores vencidos, conforme a
#            política de retenção (requisito 4.3).

set -euo pipefail

cd "$(dirname "$0")/.."

case "${1:-}" in
    ancora)
        DESTINOS="$(grep '^ANCORA_EMAIL=' .env | cut -d= -f2- || true)"
        ARGS=()
        if [ -n "$DESTINOS" ]; then
            IFS=',' read -ra LISTA <<< "$DESTINOS"
            for destino in "${LISTA[@]}"; do
                ARGS+=(--email "$(echo "$destino" | tr -d '[:space:]')")
            done
        else
            echo "[ancora] ANCORA_EMAIL vazio: a âncora fica só no servidor." >&2
        fi
        echo "[ancora] $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        docker compose exec -T web python manage.py emitir_ancora "${ARGS[@]}"
        ;;
    expurgo)
        echo "[expurgo] $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        docker compose exec -T web python manage.py expurgar
        ;;
    *)
        echo "uso: $0 ancora|expurgo" >&2
        exit 2
        ;;
esac
