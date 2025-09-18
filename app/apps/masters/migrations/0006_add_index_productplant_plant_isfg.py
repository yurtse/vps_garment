# rfc_dev/app/apps/masters/migrations/0006_add_index_productplant_plant_isfg.py
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("masters", "0005_backfill_productplant_is_fg"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="productplant",
            index=models.Index(fields=["plant_id", "is_fg"], name="masters_pp_plant_isfg_idx"),
        ),
    ]
