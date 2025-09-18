# app/apps/masters/migrations/0008_add_bomheader_snapshot_fields.py
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("masters", "0007_alter_productplant_code_alter_productplant_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="bomheader",
            name="workflow_state",
            field=models.CharField(
                choices=[("DRAFT", "Draft"), ("APPROVED", "Approved"), ("ACTIVE", "Active"), ("ARCHIVED", "Archived")],
                default="DRAFT",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="bomheader",
            name="approved_by",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to=settings.AUTH_USER_MODEL,
                related_name="+",
            ),
        ),
        migrations.AddField(
            model_name="bomheader",
            name="approved_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="bomheader",
            name="total_cost_snapshot",
            field=models.DecimalField(null=True, blank=True, max_digits=12, decimal_places=2),
        ),
        migrations.AddField(
            model_name="bomheader",
            name="immutable_snapshot",
            field=models.JSONField(null=True, blank=True),
        ),
    ]
