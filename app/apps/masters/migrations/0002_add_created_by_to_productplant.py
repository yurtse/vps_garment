# Migration: add created_by FK to ProductPlant
# Place this file under: apps/masters/migrations/0002_add_created_by_to_productplant.py

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('masters', '0004_add_style_group_to_product'),
    ]

    operations = [
        migrations.AddField(
            model_name='productplant',
            name='created_by',
            field=models.ForeignKey(
                to=settings.AUTH_USER_MODEL,
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
            ),
        ),
    ]
