# app/apps/masters/migrations/0010_add_partial_unique_index_active_bom.py
from django.db import migrations

class Migration(migrations.Migration):
    # CREATE INDEX CONCURRENTLY must not run inside a transaction
    atomic = False

    dependencies = [
        ("masters", "0011_backfill_workflow_state"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS "
                "masters_bomheader_one_active_per_pp_idx "
                "ON masters_bomheader (product_plant_id) "
                "WHERE workflow_state = 'ACTIVE';"
            ),
            reverse_sql=(
                "DROP INDEX CONCURRENTLY IF EXISTS masters_bomheader_one_active_per_pp_idx;"
            ),
        ),
    ]
