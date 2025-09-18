# apps/masters/tests/test_bom_item_uniqueness.py
from django.test import TestCase
from django.db import IntegrityError
from apps.masters.models import Product, Plant, ProductPlant, BOMHeader, BOMItem

class BOMItemUniquenessTest(TestCase):
    def setUp(self):
        self.plant = Plant.objects.create(code="PLU", name="Plant U")
        self.product = Product.objects.create(code="P-UNI", name="Prod U", product_group="RM")
        self.pp = ProductPlant.objects.create(product=self.product, plant=self.plant, code="P-UNI-PL", name="PP")
        self.bom = BOMHeader.objects.create(product_plant=self.pp, version=1)

    def test_db_rejects_duplicate_bomitem_rows(self):
        BOMItem.objects.create(bom=self.bom, component=self.pp, quantity=1)
        with self.assertRaises(IntegrityError):
            # second insert same (bom, component) must fail at DB level
            BOMItem.objects.create(bom=self.bom, component=self.pp, quantity=2)
