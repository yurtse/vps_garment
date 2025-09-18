# app/apps/masters/migrations/0011_backfill_workflow_state.py
from django.db import migrations


def forwards_func(apps, schema_editor):
    BOMHeader = apps.get_model("masters", "BOMHeader")

    # detect if the old is_active column exists on the historical model
    field_names = [f.name for f in BOMHeader._meta.get_fields()]
    has_is_active = "is_active" in field_names

    # If is_active exists, set workflow_state = 'ACTIVE' where is_active is true.
    # Otherwise, set any NULL/empty workflow_state to 'DRAFT' to ensure all rows have a value.
    if has_is_active:
        # Use two-step update to avoid loading objects into memory
        BOMHeader.objects.filter(is_active=True).update(workflow_state="ACTIVE")
        BOMHeader.objects.filter(workflow_state__isnull=True).update(workflow_state="DRAFT")
    else:
        # No is_active column — ensure existing rows get at least DRAFT if missing
        BOMHeader.objects.filter(workflow_state__isnull=True).update(workflow_state="DRAFT")


def reverse_func(apps, schema_editor):
    BOMHeader = apps.get_model("masters", "BOMHeader")
    field_names = [f.name for f in BOMHeader._meta.get_fields()]
    has_is_active = "is_active" in field_names

    if has_is_active:
        # best-effort reverse: set is_active True for rows with workflow_state ACTIVE
        BOMHeader.objects.filter(workflow_state="ACTIVE").update(is_active=True)
    # We won't undo setting DRAFT to others — leave as-is.


class Migration(migrations.Migration):

    dependencies = [
        ("masters", "0010_alter_bomitem_unique_together_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards_func, reverse_func),
    ]
