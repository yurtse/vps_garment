# app/apps/masters/migrations/0013_drop_is_active_if_exists.py
from django.db import migrations

def forwards(apps, schema_editor):
    # guard: drop column only if it exists
    schema_editor.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'masters_bomheader' AND column_name = 'is_active'
        ) THEN
            ALTER TABLE public.masters_bomheader DROP COLUMN is_active;
        END IF;
    END
    $$;
    """)

def reverse(apps, schema_editor):
    # reverse: re-add column as boolean default FALSE (best-effort)
    schema_editor.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'masters_bomheader' AND column_name = 'is_active'
        ) THEN
            ALTER TABLE public.masters_bomheader ADD COLUMN is_active boolean DEFAULT FALSE;
        END IF;
    END
    $$;
    """)

class Migration(migrations.Migration):
    dependencies = [
        ("masters", "0012_add_partial_unique_index_active_bom"),
    ]
    operations = [
        migrations.RunPython(forwards, reverse),
    ]
