# rfc_dev/app/apps/masters/tests/test_bom_concurrency.py
"""
Phase 0 — Test: BOM concurrency behavior

This TransactionTestCase simulates two concurrent creators trying to create a BOMHeader
for the same ProductPlant. The purpose is to verify that our intended versioning strategy
(using SELECT ... FOR UPDATE / short transactions) yields unique monotonic versions when
code implementing that pattern exists.

Fix note: ProductPlant requires a Plant FK (non-null). This test now creates a minimal
Plant instance and associates ProductPlant rows with it.
"""

import threading
from django.db import transaction
from django.db.models import Max
from django.test import TransactionTestCase
from django.contrib.auth import get_user_model

from apps.masters.models import Product, ProductPlant, BOMHeader, Plant


class BOMConcurrencyTestCase(TransactionTestCase):
    """
    Simulate concurrent BOMHeader creation for the same ProductPlant.

    Expected behavior (once Phase 5 is implemented):
    - versions should be unique and monotonic (1,2,...)
    - no IntegrityError for duplicate (product_plant, version)
    """

    reset_sequences = True  # ensure predictable PKs across DB backends

    def setUp(self):
        User = get_user_model()
        # create a simple user for created_by field
        self.user = User.objects.create_user(username="testuser", password="testpass")

        # create a Plant (ProductPlant requires it)
        self.plant = Plant.objects.create(code="PLANT-1", name="Plant 1")

        # Create Product and ProductPlant entries sufficient for BOM creation
        self.product = Product.objects.create(code="FG-001", name="FG Product 1", product_group="FG")
        # ProductPlant likely requires plant FK; set it now
        self.productplant = ProductPlant.objects.create(
            product=self.product,
            code="FG-001-PLANT",
            name="FG ProductPlant 1",
            plant=self.plant,  # <-- required FK
        )

    def _create_bom_version(self, result_dict, key):
        """
        Worker invoked in a separate thread to simulate a concurrent request.
        The worker:
        - opens a DB transaction
        - locks the productplant row (select_for_update)
        - computes last version and creates a new BOMHeader with version = last+1
        """
        try:
            # Open a short transaction to simulate typical save flow
            with transaction.atomic():
                # Re-fetch and lock the productplant row to serialize writers
                locked_pp = ProductPlant.objects.select_for_update().get(pk=self.productplant.pk)

                last_version = BOMHeader.objects.filter(product_plant=locked_pp).aggregate(
                    Max("version")
                )["version__max"] or 0

                new_version = last_version + 1

                # Create the BOMHeader (minimal required fields)
                bom = BOMHeader.objects.create(
                    product_plant=locked_pp,
                    version=new_version,
                    created_by=self.user,
                )

            # store success result
            result_dict[key] = {"ok": True, "version": bom.version}
        except Exception as exc:
            # store exception to inspect if the creation failed
            result_dict[key] = {"ok": False, "exc": exc}

    def test_concurrent_bom_creates_produce_unique_versions(self):
        # dictionary to gather thread results
        results = {}

        # spawn two threads that attempt to create a BOM almost simultaneously
        threads = [
            threading.Thread(target=self._create_bom_version, args=(results, 1)),
            threading.Thread(target=self._create_bom_version, args=(results, 2)),
        ]

        # start threads
        for t in threads:
            t.start()

        # wait for completion
        for t in threads:
            t.join()

        # Collect results
        self.assertIn(1, results)
        self.assertIn(2, results)

        # Ensure both operations succeeded
        self.assertTrue(results[1]["ok"], msg=f"Thread 1 failed: {results[1]}")
        self.assertTrue(results[2]["ok"], msg=f"Thread 2 failed: {results[2]}")

        v1 = results[1]["version"]
        v2 = results[2]["version"]

        # Expect unique versions. The exact ordering (1 vs 2) is not strictly assumed,
        # but uniqueness is required.
        self.assertNotEqual(v1, v2, msg=f"Versions must be unique: v1={v1}, v2={v2}")

        # Also assert that both versions exist in DB for this product_plant
        versions_in_db = sorted(
            list(BOMHeader.objects.filter(product_plant=self.productplant).values_list("version", flat=True))
        )
        self.assertIn(v1, versions_in_db)
        self.assertIn(v2, versions_in_db)
