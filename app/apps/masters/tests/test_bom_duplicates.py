# rfc_dev/app/apps/masters/tests/test_bom_duplicates.py
"""
Phase 0 — Test: BOMItem duplicate prevention (DB safety net)

This test asserts that the database (or model constraints) prevents two BOMItem rows
having the same (bom_id, component_id). If the unique constraint is not present in
your current schema this test will fail — that's intentional: it surfaces the missing
non-negotiable safety-net (Phase 7 task to add DB unique constraint).

Notes:
- Uses the correct BOMItem field names from your code: `component` and `quantity`.
- Creates a minimal Plant for ProductPlant FK requirement.
"""

from django.test import TransactionTestCase
from django.db import IntegrityError
from django.contrib.auth import get_user_model

from apps.masters.models import Product, ProductPlant, BOMHeader, BOMItem, Plant


class BOMDuplicateItemTestCase(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="dupuser", password="testpass2")

        # create a Plant (ProductPlant requires it)
        self.plant = Plant.objects.create(code="PLANT-1", name="Plant 1")

        # create FG product and productplant
        self.fg_product = Product.objects.create(code="FG-DUP-001", name="FG Dup", product_group="FG")
        self.fg_pp = ProductPlant.objects.create(
            product=self.fg_product,
            code="FGD-PL",
            name="FG Dup PP",
            plant=self.plant,  # required FK
        )

        # create a component product and productplant (non-FG)
        self.comp_product = Product.objects.create(code="RM-001", name="RM 1", product_group="RM")
        self.comp_pp = ProductPlant.objects.create(
            product=self.comp_product,
            code="RM-001-PL",
            name="RM 1 PP",
            plant=self.plant,  # same plant for component
        )

        # create a BOMHeader
        self.bom = BOMHeader.objects.create(product_plant=self.fg_pp, version=1, created_by=self.user)

    def test_db_rejects_duplicate_bomitem_rows(self):
        # Create the first BOMItem using correct field names
        BOMItem.objects.create(bom=self.bom, component=self.comp_pp, quantity=1)

        # Attempt to create the duplicate BOMItem — expect IntegrityError if DB unique constraint exists
        with self.assertRaises(IntegrityError):
            BOMItem.objects.create(bom=self.bom, component=self.comp_pp, quantity=2)
