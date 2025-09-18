import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.masters.models import Product, ProductPlant, Plant
from apps.masters.services.productplant_seed import seed_productplants

@pytest.mark.django_db
def test_non_superuser_without_plant_cannot_seed(client, django_user_model):
    user = django_user_model.objects.create_user(username="u1", password="pass")
    client.login(username="u1", password="pass")
    url = reverse('admin:masters_productplant_seed')
    resp = client.post(url, {})
    assert resp.status_code in (302, 403)  # should redirect with error or forbidden

@pytest.mark.django_db
def test_normal_user_seeds_selected_products(client, django_user_model):
    User = get_user_model()
    user = User.objects.create_user(username="tester", password="pass")
    # create plant and attach to a simple userprofile if your project uses userprofile; adapt if necessary
    plant = Plant.objects.create(name="TestPlant", code="PLT1")
    # attach plant to userprofile if required; this test assumes user.userprofile.plant exists
    try:
        user.userprofile.plant = plant
        user.userprofile.save()
    except Exception:
        # if no userprofile model, skip attaching: set up test to use superuser instead
        pass

    p1 = Product.objects.create(code="PX1", name="Prod X1")
    p2 = Product.objects.create(code="PX2", name="Prod X2")

    client.login(username="tester", password="pass")
    url = reverse('admin:masters_productplant_seed') + f"?plant={plant.pk}"
    # Post selected items
    resp = client.post(url, {'selected_pks': [str(p1.pk), str(p2.pk)], 'plant': plant.pk})
    # After redirect, ensure ProductPlant rows exist
    assert ProductPlant.objects.filter(plant=plant, product__in=[p1, p2]).count() == 2

@pytest.mark.django_db
def test_superuser_can_seed_by_choosing_plant(client, django_user_model):
    User = get_user_model()
    admin = User.objects.create_superuser('admin2', 'admin2@example.com', 'pass')
    plant = Plant.objects.create(name="TestPlant2", code="PLT2")
    p1 = Product.objects.create(code="PX3", name="Prod X3")
    client.login(username='admin2', password='pass')
    url = reverse('admin:masters_productplant_seed')
    resp = client.post(url, {'selected_pks': [str(p1.pk)], 'plant': plant.pk})
    assert ProductPlant.objects.filter(plant=plant, product=p1).exists()
