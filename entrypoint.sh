#!/usr/bin/env sh
set -e

# Wait for DB if WAIT_FOR_DB is set (simple wait loop)
if [ -n "$WAIT_FOR_DB" ]; then
  echo "Waiting for DB ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}..."
  # simple wait-for loop (you can use wait-for-it or dockerize for advanced logic)
  COUNTER=0
  until nc -z ${POSTGRES_HOST:-db} ${POSTGRES_PORT:-5432} || [ $COUNTER -ge 30 ]; do
    echo "  waiting for db... ($COUNTER)"
    COUNTER=$((COUNTER+1))
    sleep 2
  done
fi

# Run migrations and collectstatic (safe for idempotent runs)
echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput || true

# Exec the container CMD (gunicorn) as PID 1
exec "$@"
