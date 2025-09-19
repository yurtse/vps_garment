# app/apps/masters/migrations/0015_change_productplant_code_uniqueness.py
from django.db import migrations

DROP_CONSTRAINT = """
ALTER TABLE public.masters_productplant
  DROP CONSTRAINT IF EXISTS masters_productplant_code_20654171_uniq;
"""

ADD_CONSTRAINT = """
ALTER TABLE public.masters_productplant
  ADD CONSTRAINT masters_productplant_plant_code_uniq UNIQUE (plant_id, code);
"""

CREATE_INDEX = """
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind = 'i' AND c.relname = 'masters_pp_plant_isfg_idx'
  ) THEN
    CREATE INDEX masters_pp_plant_isfg_idx
    ON public.masters_productplant (plant_id, is_fg);
  END IF;
END;
$$;
"""

class Migration(migrations.Migration):

    dependencies = [
        ("masters", "0014_add_bom_effective_range_exclusion"),
    ]

    operations = [
        # Drop the global UNIQUE(code)
        migrations.RunSQL(
            sql=DROP_CONSTRAINT,
            reverse_sql=ADD_CONSTRAINT,
        ),
        # Add the per-plant UNIQUE(plant_id, code)
        migrations.RunSQL(
            sql=ADD_CONSTRAINT,
            reverse_sql=DROP_CONSTRAINT,
        ),
        # Ensure the performance index exists
        migrations.RunSQL(
            sql=CREATE_INDEX,
            reverse_sql="DROP INDEX IF EXISTS masters_pp_plant_isfg_idx;",
        ),
    ]
