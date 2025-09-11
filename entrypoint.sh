#!/bin/sh
set -e

# Optionally wait for DB to be reachable when WAIT_FOR_DB is set
if [ -n "$WAIT_FOR_DB" ]; then
  echo "Waiting for DB ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}..."
  until python - <<PY >/dev/null 2>&1
import os,sys,socket
h=os.environ.get('POSTGRES_HOST','db')
p=int(os.environ.get('POSTGRES_PORT','5432'))
try:
    s=socket.create_connection((h,p),2); s.close(); print("ok")
except Exception:
    sys.exit(1)
PY
  do
    echo "DB not reachable yet - sleeping 2s"
    sleep 2
  done
fi

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

# Execute passed commands (gunicorn by default)
exec "$@"
