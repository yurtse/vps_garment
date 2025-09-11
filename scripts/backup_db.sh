#!/bin/sh
set -e
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
mkdir -p ./backups
# uses docker-compose service name 'db'
docker compose exec -T db pg_dumpall -U "${POSTGRES_USER:-postgres}" > ./backups/db_backup_$TIMESTAMP.sql
echo "Backup written to ./backups/db_backup_$TIMESTAMP.sql"
