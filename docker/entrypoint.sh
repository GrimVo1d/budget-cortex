#!/usr/bin/env bash
# Entrypoint dispatcher.
#   entrypoint.sh api               — gunicorn on :8000
#   entrypoint.sh worker [queues]   — celery worker (default: "default,low")
#   entrypoint.sh beat              — celery beat
#   entrypoint.sh migrate           — django migrate
#   entrypoint.sh <anything else>   — exec it as-is (e.g. python manage.py shell)
set -euo pipefail

cmd="${1:-api}"
shift || true

case "$cmd" in
    api)
        exec gunicorn budget_cortex.wsgi:application \
            --bind 0.0.0.0:8000 \
            --no-control-socket \
            --workers "${GUNICORN_WORKERS:-4}" \
            --timeout "${GUNICORN_TIMEOUT:-30}" \
            --access-logfile - \
            --error-logfile -
        ;;
    worker)
        queues="${1:-default,low}"
        exec celery -A budget_cortex worker \
            -Q "$queues" \
            -n "worker@%h" \
            --concurrency "${CELERY_CONCURRENCY:-4}" \
            --loglevel "${CELERY_LOG_LEVEL:-INFO}"
        ;;
    beat)
        exec celery -A budget_cortex beat \
            --schedule /tmp/celerybeat-schedule \
            --loglevel "${CELERY_LOG_LEVEL:-INFO}"
        ;;
    migrate)
        exec python manage.py migrate --noinput
        ;;
    *)
        exec "$cmd" "$@"
        ;;
esac
