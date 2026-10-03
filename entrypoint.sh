#!/usr/bin/env bash
#
# Roda a cada subida do container, antes do Gunicorn.
# Precisa ser idempotente: todo deploy passa por aqui de novo.

set -euo pipefail

echo "[entrypoint] esperando o banco responder..."
until python -c "
import sys, psycopg, os
try:
    psycopg.connect(
        dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD'], host=os.environ['DB_HOST'],
        port=os.environ.get('DB_PORT', '5432'), connect_timeout=3,
    ).close()
except Exception:
    sys.exit(1)
" 2>/dev/null; do
    sleep 1
done
echo "[entrypoint] banco respondendo"

echo "[entrypoint] aplicando migracoes"
python manage.py migrate --noinput

echo "[entrypoint] coletando arquivos estaticos"
python manage.py collectstatic --noinput --clear

echo "[entrypoint] subindo o Gunicorn"
# 3 workers e um ponto de partida razoavel pra 1 vCPU. O timeout maior
# que o padrao acomoda o Argon2id, que leva algumas centenas de ms por
# login de proposito.
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
