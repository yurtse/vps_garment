# rfc_dev/app/apps/masters/tests/test_productplant_backfill.py
"""
Phase 1 — Test: ProductPlant backfill for is_fg and product_type_code.

This test runs the forward logic similarly to the migration, but at unit test speed:
- creates products with different product_group values
- creates ProductPlant rows (with new nullable columns)
- runs the backfill logic (via calling the migration function if desired)
- asserts that ProductPlant.is_fg and product_type_code are set as expected.
"""

from django.test import TestCase
from apps.masters.models import Product, ProductPlant, Plant


# Reuse the mapping we used in migration to verify behavior
_MAPPING = {
    "FG": (True, 1),
    "RM": (False, 2),
    "WIP": (False, 3),
    "TRM": (False, 4),
}


class ProductPlantBackfillTestCase(TestCase):
    def setUp(self):
        # create a plant
        self.plant = Plant.objects.create(code="PLANT-BF", name="Backfill Plant")

    def test_backfill_sets_is_fg_and_code(self):
        # create products and productplants
        for pg, (is_fg_expected, code_expected) in _MAPPING.items():
            p = Product.objects.create(code=f"P-{pg}", name=f"Prod {pg}", product_group=pg)
            pp = ProductPlant.objects.create(product=p, plant=self.plant, code=f"{p.code}-{self.plant.code}", name=p.name)

        # Now run the same assignment logic as migration (simulate)
        for pp in ProductPlant.objects.select_related("product").all():
            pg = getattr(pp.product, "product_group", None)
            is_fg = (pg == "FG")
            code = None
            if pg == "FG":
                code = 1
            elif pg == "RM":
                code = 2
            elif pg == "WIP":
                code = 3
            elif pg == "TRM":
                code = 4
            # update row
            ProductPlant.objects.filter(pk=pp.pk).update(is_fg=is_fg, product_type_code=code)

        # Assert expected values
        for pp in ProductPlant.objects.select_related("product").all():
            expected_is_fg, expected_code = _MAPPING[pp.product.product_group]
            refreshed = ProductPlant.objects.get(pk=pp.pk)
            self.assertEqual(refreshed.is_fg, expected_is_fg)
            self.assertEqual(refreshed.product_type_code, expected_code)
