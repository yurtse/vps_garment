#!/bin/sh
set -e
# on dev VPS: pull latest and restart containers
git fetch --all
git reset --hard origin/main
docker compose pull || true
docker compose up -d --build
docker compose exec web python manage.py migrate --noinput
docker compose exec web python manage.py collectstatic --noinput
