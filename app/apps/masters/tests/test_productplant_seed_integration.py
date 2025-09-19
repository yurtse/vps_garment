# apps/masters/tests/test_productplant_seed_integration.py
import pytest
from decimal import Decimal
import django
django.setup()

from django.contrib.auth import get_user_model
from apps.masters.models import Product, Plant, ProductPlant
from apps.masters.services.productplant_seed import seed_productplants

User = get_user_model()


@pytest.mark.django_db
def test_seed_product_into_multiple_plants_and_verify_output(capfd):
    """
    Integration-style test:
      - create two products and two plants in the test DB
      - call seed_productplants(products, plants, created_by=user)
      - assert ProductPlant rows created for each (product, plant)
      - print verification table (product_code, plant_code, pp_id) to stdout
    Running pytest with -s will let you see the printed verification (test DB output).
    """
    # create a user
    user = User.objects.create(username="seed_integ_user")

    # create products
    p1 = Product.objects.create(code="ITST100", name="Integration Test 100", uom="pcs", standard_cost=Decimal("11.11"))
    # add a second product to exercise multiple-product case
    p2 = Product.objects.create(code="ITST200", name="Integration Test 200", uom="pcs", standard_cost=Decimal("22.22"))

    # create two plants
    pl_a = Plant.objects.create(name="Integration Plant A", code="INT-PL-A")
    pl_b = Plant.objects.create(name="Integration Plant B", code="INT-PL-B")

    # Sanity pre-check: no ProductPlant rows for these products
    assert ProductPlant.objects.filter(product__in=[p1, p2]).count() == 0

    # Run seeding
    summary = seed_productplants([p1, p2], [pl_a, pl_b], created_by=user)

    # Validate summary structure and values exist
    assert isinstance(summary, dict)
    assert "plants" in summary and summary["plants"], "summary must include per-plant entries"

    # Assert DB rows: 2 products * 2 plants => 4 ProductPlant rows
    qs = ProductPlant.objects.filter(product__in=[p1, p2]).order_by("product_id", "plant_id")
    rows = list(qs)
    assert len(rows) == 4, f"Expected 4 ProductPlant rows but found {len(rows)}"

    # For stronger checks, ensure each (product, plant) exists exactly once
    for prod in (p1, p2):
        for pl in (pl_a, pl_b):
            assert ProductPlant.objects.filter(product=prod, plant=pl).exists()

    # Print verification table (visible when running pytest -s)
    print("\n=== Seed Verification (test DB) ===")
    print("pp_id | product_code | plant_code | created_by")
    for pp in rows:
        created_by = getattr(pp, "created_by", None)
        created_by_name = created_by.username if created_by else "None"
        print(f"{pp.pk} | {pp.product.code} | {pp.plant.code} | {created_by_name}")

    # Re-run seeding on same products/plants to check idempotency (should not create new rows)
    summary2 = seed_productplants([p1, p2], [pl_a, pl_b], created_by=user)
    # no new created rows after second run
    created_after_second = ProductPlant.objects.filter(product__in=[p1, p2]).count()
    assert created_after_second == 4, "Re-running seed should not create duplicates"
