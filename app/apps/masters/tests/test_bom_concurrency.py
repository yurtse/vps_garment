# apps/masters/tests/test_bom_concurrency.py
import threading
from django.test import TransactionTestCase
from django.db import connection
from apps.masters.models import Product, Plant, ProductPlant, BOMHeader

class BOMConcurrencyTestCase(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.plant = Plant.objects.create(code="PLC", name="Plant C")
        self.product = Product.objects.create(code="P-CONC", name="Prod C", product_group="FG")
        self.pp = ProductPlant.objects.create(product=self.product, plant=self.plant, code="P-CONC-PL", name="PP C")

    def _create_bom_thread(self, results, idx, start_barrier):
        # ensure this thread uses a fresh DB connection
        connection.close()
        start_barrier.wait()
        # call the concurrency-safe factory
        b = BOMHeader.create_with_next_version(self.pp, effective_from=None, effective_to=None)
        results[idx] = b.version

    def test_concurrent_bom_creates_produce_unique_versions(self):
        threads = []
        n = 4
        results = [None] * n
        start = threading.Barrier(n)
        for i in range(n):
            t = threading.Thread(target=self._create_bom_thread, args=(results, i, start))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()

        # all versions should be unique
        assert len(set(results)) == n, f"versions not unique: {results}"
        # and they should be sequential starting from 1 (or from next available)
        self.assertEqual(sorted(results), list(range(1, n+1)))
