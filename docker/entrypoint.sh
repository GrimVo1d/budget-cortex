#!/usr/bin/env bash
# Entrypoint dispatcher.
#   entrypoint.sh api               — gunicorn on :8000
#   entrypoint.sh worker [queue]    — celery worker for "default" (or named) queue
#   entrypoint.sh beat              — celery beat
#   entrypoint.sh migrate           — django migrate
#   entrypoint.sh shell             — django shell
set -euo pipefail

cmd="${1:-api}"
shift || true

case "$cmd" in
    api)
        exec gunicorn budget_cortex.wsgi:application \
            --bind 0.0.0.0:8000 \
            --workers "${GUNICORN_WORKERS:-4}" \
            --timeout "${GUNICORN_TIMEOUT:-30}" \
            --access-logfile - \
            --error-logfile -
        ;;
    worker)
        queue="${1:-default}"
        exec celery -A budget_cortex worker \
            -Q "$queue" \
            -n "${queue}@%h" \
            --concurrency "${CELERY_CONCURRENCY:-4}" \
            --loglevel "${CELERY_LOG_LEVEL:-INFO}"
        ;;
    beat)
        exec celery -A budget_cortex beat \
            --loglevel "${CELERY_LOG_LEVEL:-INFO}"
        ;;
    migrate)
        exec python manage.py migrate --noinput
        ;;
    shell)
        exec python manage.py shell
        ;;
    bash|sh)
        exec /bin/bash
        ;;
    *)
        exec "$cmd" "$@"
        ;;
esac
