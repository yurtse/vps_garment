"""
Service helpers for ProductPlant seeding and compatibility helpers.

Place this file under: apps/masters/services/productplant_seed.py

Contains:
- get_products_missing_for_plant(plant, filters=None)
- get_products_missing_for_plants(plants, filters=None)
- seed_productplants(products, plants, created_by)
- resolve_product_and_plant_from_instance(instance)
"""

from typing import Iterable, Dict, List, Optional, Tuple, Any
from django.db import transaction, IntegrityError
from django.db.models import Exists, OuterRef, QuerySet
from django.contrib.auth import get_user_model

from apps.masters.models import Product, ProductPlant, Plant, ProductGroup

User = get_user_model()


def get_products_missing_for_plant(plant: Plant, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
    """Return a QuerySet of Product objects that do NOT have a ProductPlant for the given plant."""
    products = Product.objects.all()
    if filters:
        products = products.filter(**filters)

    pp_qs = ProductPlant.objects.filter(product=OuterRef('pk'), plant=plant)
    missing_qs = products.annotate(_pp_exists=Exists(pp_qs)).filter(_pp_exists=False)
    return missing_qs


def get_products_missing_for_plants(plants: Iterable[Plant], filters: Optional[Dict[str, Any]] = None) -> Dict[int, QuerySet]:
    """Return dict mapping plant.id -> QuerySet of missing products for that plant."""
    result: Dict[int, QuerySet] = {}
    for plant in plants:
        result[plant.id] = get_products_missing_for_plant(plant, filters=filters)
    return result


def _normalize_products_arg(products: Iterable) -> List[Product]:
    """Normalize the `products` argument to a list of Product instances."""
    if isinstance(products, QuerySet):
        return list(products)

    products_list: List[Product] = []
    for p in products:
        if isinstance(p, Product):
            products_list.append(p)
        elif isinstance(p, int):
            products_list.append(Product.objects.get(pk=p))
        else:
            raise TypeError("products must contain Product instances or int PKs")
    return products_list


def _normalize_plants_arg(plants: Iterable) -> List[Plant]:
    """Normalize the `plants` argument to a list of Plant instances."""
    plant_list: List[Plant] = []
    for pl in plants:
        if isinstance(pl, Plant):
            plant_list.append(pl)
        elif isinstance(pl, int):
            plant_list.append(Plant.objects.get(pk=pl))
        else:
            raise TypeError("plants must contain Plant instances or int PKs")
    return plant_list


def _filter_valid_pp_kwargs(candidate_kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only keys that are actual fields on ProductPlant model."""
    model_field_names = {f.name for f in ProductPlant._meta.get_fields() if getattr(f, 'column', None) is not None}
    return {k: v for k, v in candidate_kwargs.items() if k in model_field_names}


def seed_productplants(products: Iterable, plants: Iterable, created_by: Optional[User]) -> Dict[str, Any]:
    """Seed ProductPlant rows for given products into given plants.

    Phase 1: non-invasive enhancement
    - Populate denormalized fields `is_fg` and `product_type_code` on ProductPlant candidates.
    - These fields are added to the candidate kwargs only; they are nullable in DB so this is safe.
    - The public function signature and behavior are unchanged; bulk_create and per-instance save fallback remain.
    """
    products_list = _normalize_products_arg(products)
    plants_list = _normalize_plants_arg(plants)
    prod_pks = [p.pk for p in products_list]

    # mapping from ProductGroup (enum/value) to small int codes used for product_type_code
    # adjust codes to match your conventions if needed
    _GROUP_TO_CODE = {
        # using enum members if ProductGroup is an enum in models
        getattr(ProductGroup, "FINISHED_GOOD", "FG"): 1,
        getattr(ProductGroup, "RAW_MATERIAL", "RM"): 2,
        getattr(ProductGroup, "WIP", "WIP"): 3,
        getattr(ProductGroup, "TRIMS", "TRM"): 4,
        # also support string keys as fallback
        "FG": 1,
        "RM": 2,
        "WIP": 3,
        "TRM": 4,
    }

    summary: Dict[str, Any] = {'total_products': len(prod_pks), 'plants': {}}

    with transaction.atomic():
        for plant in plants_list:
            plant_summary = {
                'plant_id': plant.id,
                'plant_name': getattr(plant, 'name', str(plant.id)),
                'created': 0,
                'skipped': 0,
                'failed': 0,
                'created_pks': [],
                'skipped_pks': [],
                'failed_details': [],
            }

            existing_pp = ProductPlant.objects.filter(
                product_id__in=prod_pks, plant=plant
            ).values_list('product_id', flat=True)
            existing_set = set(existing_pp)

            to_create: List[ProductPlant] = []
            now_create_products: List[Product] = []
            for p in products_list:
                if p.pk in existing_set:
                    plant_summary['skipped'] += 1
                    plant_summary['skipped_pks'].append(p.pk)
                    continue

                candidate_kwargs: Dict[str, Any] = {
                    'product': p,
                    'plant': plant,
                    'code': getattr(p, 'code', ''),
                    'name': getattr(p, 'name', ''),
                    'standard_cost': getattr(p, 'standard_cost', None) or 0,
                    'active': True,
                }
                if created_by is not None:
                    candidate_kwargs['created_by'] = created_by

                # ----------------- Phase 1 additions (denormalized fields) -----------------
                # Determine product_group value (support enum member or string)
                pg = getattr(p, 'product_group', None)

                # is_fg: True if product_group indicates Finished Good (safe fallback to string 'FG')
                try:
                    is_fg_val = (pg == ProductGroup.FINISHED_GOOD) or (str(pg).upper().startswith("FG"))
                except Exception:
                    # fallback: compare as string
                    is_fg_val = (str(pg).upper().startswith("FG")) if pg is not None else None
                candidate_kwargs['is_fg'] = is_fg_val

                # product_type_code: map using _GROUP_TO_CODE with resilient lookups
                code_val = None
                try:
                    # try exact enum/key match first
                    code_val = _GROUP_TO_CODE.get(pg)
                except Exception:
                    code_val = None
                if code_val is None and pg is not None:
                    code_val = _GROUP_TO_CODE.get(str(pg).upper())
                candidate_kwargs['product_type_code'] = code_val
                # -------------------------------------------------------------------------

                pp_kwargs = _filter_valid_pp_kwargs(candidate_kwargs)
                pp = ProductPlant(**pp_kwargs)
                to_create.append(pp)
                now_create_products.append(p)

            if to_create:
                try:
                    ProductPlant.objects.bulk_create(to_create)
                    plant_summary['created'] = len(to_create)
                    plant_summary['created_pks'] = [p.pk for p in now_create_products]
                except Exception as exc:
                    # fallback to per-instance save to collect granular failures
                    for idx, pp in enumerate(to_create):
                        try:
                            pp.save()
                            plant_summary['created'] += 1
                            plant_summary['created_pks'].append(now_create_products[idx].pk)
                        except IntegrityError as ie:
                            plant_summary['failed'] += 1
                            plant_summary['failed_details'].append({'product_pk': now_create_products[idx].pk, 'error': str(ie)})
                        except Exception as e:
                            plant_summary['failed'] += 1
                            plant_summary['failed_details'].append({'product_pk': now_create_products[idx].pk, 'error': str(e)})

            summary['plants'][plant.id] = plant_summary

    return summary



def resolve_product_and_plant_from_instance(instance) -> Tuple[Optional[Product], Optional[Plant]]:
    """Compatibility helper to resolve (Product, Plant) from an instance that may reference ProductPlant."""
    if hasattr(instance, 'product') and instance.product is not None:
        return instance.product, getattr(instance, 'plant', None)

    if hasattr(instance, 'product_code') and getattr(instance, 'product_code'):
        code = getattr(instance, 'product_code')
        try:
            prod = Product.objects.get(code=code)
        except Product.DoesNotExist:
            prod = None
        return prod, getattr(instance, 'plant', None)

    for field in ['productplant', 'product_plant', 'productplant_id', 'product_plant_id']:
        if hasattr(instance, field):
            pp_val = getattr(instance, field)
            if isinstance(pp_val, ProductPlant):
                return pp_val.product, pp_val.plant
            if isinstance(pp_val, int) or (isinstance(pp_val, str) and pp_val.isdigit()):
                try:
                    pp = ProductPlant.objects.select_related('product', 'plant').get(pk=int(pp_val))
                    return pp.product, pp.plant
                except ProductPlant.DoesNotExist:
                    pass

    return None, None
