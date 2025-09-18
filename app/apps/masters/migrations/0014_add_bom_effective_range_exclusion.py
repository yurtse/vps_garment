# app/apps/masters/migrations/0014_add_bom_effective_range_exclusion.py
from django.db import migrations

class Migration(migrations.Migration):
    # Exclusion constraint / CREATE INDEX CONCURRENTLY cannot run inside a transaction.
    atomic = False

    dependencies = [
        ("masters", "0013_drop_is_active_if_exists"),  # adjust if your last migration name differs
    ]

    operations = [
        # 1) ensure btree_gist available so we can have gist equality on product_plant_id
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS btree_gist;",
            reverse_sql="DROP EXTENSION IF EXISTS btree_gist;"
        ),

        # 2) add exclusion constraint preventing overlapping date ranges for ACTIVE BOMs
        #    This uses POSTGRES exclusion with gist: product_plant_id = AND range && range
        migrations.RunSQL(
            sql=(
                "ALTER TABLE public.masters_bomheader "
                "ADD CONSTRAINT masters_bomheader_no_overlap_active EXCLUDE USING GIST "
                "(product_plant_id WITH =, daterange(effective_from, effective_to, '[]') WITH &&) "
                "WHERE (workflow_state = 'ACTIVE');"
            ),
            reverse_sql=(
                "ALTER TABLE public.masters_bomheader "
                "DROP CONSTRAINT IF EXISTS masters_bomheader_no_overlap_active;"
            ),
        ),
    ]
