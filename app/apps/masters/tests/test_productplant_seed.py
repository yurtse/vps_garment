# Place this file at: apps/masters/tests/test_productplant_seed.py
# Run with: docker-compose run --rm web pytest -q ./apps/masters/tests/test_productplant_seed.py

import pytest
from django.contrib.auth import get_user_model

from apps.masters.models import Product, ProductPlant, Plant
from apps.masters.services.productplant_seed import (
    get_products_missing_for_plant,
    get_products_missing_for_plants,
    seed_productplants,
    resolve_product_and_plant_from_instance,
)


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(username="tester", password="pass")


@pytest.fixture
def plant(db):
    try:
        return Plant.objects.create(name="Test Plant", code="PLANT-TEST")
    except TypeError:
        return Plant.objects.create(name="Test Plant")


@pytest.fixture
def products(db):
    p1 = Product.objects.create(code="P100", name="Prod 100")
    p2 = Product.objects.create(code="P200", name="Prod 200")
    p3 = Product.objects.create(code="P300", name="Prod 300")
    return p1, p2, p3


@pytest.mark.django_db
def test_get_products_missing_for_plant(products, plant):
    p1, p2, p3 = products
    ProductPlant.objects.create(product=p1, plant=plant, code=p1.code, name=p1.name, standard_cost=p1.standard_cost, active=True)

    missing_qs = get_products_missing_for_plant(plant)
    missing_codes = {p.code for p in missing_qs}

    assert p1.code not in missing_codes
    assert p2.code in missing_codes
    assert p3.code in missing_codes
    assert missing_qs.count() == 2


@pytest.mark.django_db
def test_get_products_missing_for_plants(products, plant):
    p1, p2, p3 = products
    try:
        plant_b = Plant.objects.create(name="Test Plant B", code="PLANT-B")
    except TypeError:
        plant_b = Plant.objects.create(name="Test Plant B")

    ProductPlant.objects.create(product=p1, plant=plant, code=p1.code, name=p1.name, standard_cost=p1.standard_cost, active=True)

    result = get_products_missing_for_plants([plant, plant_b])
    missing_for_plant_codes = {p.code for p in result[plant.id]}
    missing_for_plant_b_codes = {p.code for p in result[plant_b.id]}

    assert p2.code in missing_for_plant_codes
    assert {p1.code, p2.code, p3.code} == missing_for_plant_b_codes


@pytest.mark.django_db
def test_seed_productplants_creates_and_skips(products, plant, user):
    p1, p2, p3 = products
    ProductPlant.objects.create(product=p1, plant=plant, code=p1.code, name=p1.name, standard_cost=p1.standard_cost, active=True)

    summary = seed_productplants([p1, p2], [plant], created_by=user)
    plant_summary = summary["plants"][plant.id]

    assert plant_summary["created"] == 1
    assert plant_summary["skipped"] == 1

    cnt = ProductPlant.objects.filter(plant=plant, product__in=[p1.pk, p2.pk]).count()
    assert cnt == 2

    field_names = {f.name for f in ProductPlant._meta.get_fields()}
    if 'created_by' in field_names:
        created_pp = ProductPlant.objects.get(product=p2, plant=plant)
        assert getattr(created_pp, 'created_by') == user


@pytest.mark.django_db
def test_seed_productplants_idempotent(products, plant, user):
    p1, p2, p3 = products
    summary1 = seed_productplants([p1, p2], [plant], created_by=user)
    plant_summary1 = summary1["plants"][plant.id]
    assert plant_summary1["created"] >= 1

    summary2 = seed_productplants([p1, p2], [plant], created_by=user)
    plant_summary2 = summary2["plants"][plant.id]
    assert plant_summary2["created"] == 0
    assert plant_summary2["skipped"] >= 1

    db_count = ProductPlant.objects.filter(plant=plant, product__pk__in=[p1.pk, p2.pk]).count()
    assert db_count == plant_summary1["created"] + plant_summary1["skipped"]


@pytest.mark.django_db
def test_resolve_product_and_plant_from_instance(products, plant):
    p1, p2, p3 = products

    class ObjA: pass
    a = ObjA(); a.product = p1; a.plant = plant
    prod, pl = resolve_product_and_plant_from_instance(a)
    assert prod == p1 and pl == plant

    class ObjB: pass
    b = ObjB(); b.product_code = p2.code; b.plant = plant
    prod2, pl2 = resolve_product_and_plant_from_instance(b)
    assert prod2 == p2 and pl2 == plant

    pp = ProductPlant.objects.create(product=p3, plant=plant, code=p3.code, name=p3.name, standard_cost=p3.standard_cost, active=True)
    class ObjC: pass
    c = ObjC(); c.productplant = pp
    prod3, pl3 = resolve_product_and_plant_from_instance(c)
    assert prod3 == p3 and pl3 == plant
