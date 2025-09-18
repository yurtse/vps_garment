# rfc_dev/app/apps/masters/migrations/0005_backfill_productplant_is_fg.py
from django.db import migrations

def forwards_func(apps, schema_editor):
    ProductPlant = apps.get_model("masters", "ProductPlant")
    Product = apps.get_model("masters", "Product")

    # mapping of textual product_group values -> small int codes
    mapping = {
        "FG": 1,   # Finished Good
        "RM": 2,   # Raw Material
        "WIP": 3,  # Work in Progress
        "TRM": 4,  # Trims/Accessories
        # Add more keys here if your product_group values differ
    }

    # Iterate and update rows in a way that avoids loading everything into memory at once.
    qs = ProductPlant.objects.select_related("product").all()
    for pp in qs.iterator():
        pg = getattr(pp.product, "product_group", None)
        # Determine is_fg (support enum-like or string values)
        is_fg = False
        if pg is not None:
            # If ProductGroup is an enum member, it may compare directly; else compare string prefixes.
            try:
                is_fg = (pg == "FG") or (str(pg).upper().startswith("FG"))
            except Exception:
                is_fg = str(pg).upper().startswith("FG")
        # Determine product_type_code
        code = None
        if pg is not None:
            code = mapping.get(str(pg).upper())
        # Update only the two columns to avoid touching other fields
        ProductPlant.objects.filter(pk=pp.pk).update(is_fg=is_fg, product_type_code=code)


def reverse_func(apps, schema_editor):
    ProductPlant = apps.get_model("masters", "ProductPlant")
    ProductPlant.objects.all().update(is_fg=None, product_type_code=None)


class Migration(migrations.Migration):

    dependencies = [
        ("masters", "0004_alter_productplant_options_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards_func, reverse_func),
    ]
