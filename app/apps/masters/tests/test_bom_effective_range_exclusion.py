# apps/masters/tests/test_bom_effective_range_exclusion.py
from django.test import TransactionTestCase
from django.db import IntegrityError
from apps.masters.models import Plant, Product, ProductPlant, BOMHeader

class BOMEffectiveRangeExclusionTest(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.plant = Plant.objects.create(code="PLX", name="Plant X")
        self.product = Product.objects.create(code="PX", name="Prod X", product_group="FG")
        self.pp = ProductPlant.objects.create(product=self.product, plant=self.plant, code="PX-PL", name="PX PL")
    
    def test_db_rejects_overlapping_active_ranges(self):
        # create two headers with overlapping date ranges
        a = BOMHeader.objects.create(product_plant=self.pp, version=1, effective_from="2025-01-01", effective_to="2025-12-31", workflow_state="DRAFT")
        b = BOMHeader.objects.create(product_plant=self.pp, version=2, effective_from="2025-06-01", effective_to="2025-06-30", workflow_state="DRAFT")
        # activate first
        BOMHeader.objects.filter(pk=a.pk).update(workflow_state="ACTIVE")
        # activating second should raise an IntegrityError due to DB constraint
        with self.assertRaises(Exception):
            BOMHeader.objects.filter(pk=b.pk).update(workflow_state="ACTIVE")
