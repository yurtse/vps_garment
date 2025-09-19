# apps/masters/views.py
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q

from .models import ProductPlant


def fg_autocomplete(request):
    """
    Return plant-scoped Finished Goods for autocomplete dropdown.
    Query params: ?q=term&page=N
    """
    term = request.GET.get("q", "").strip()
    page = int(request.GET.get("page", 1))

    qs = ProductPlant.objects.filter(is_fg=True, active=True)
    if term:
        qs = qs.filter(
            Q(product__name__icontains=term) | Q(product__code__icontains=term)
        ).order_by("product__name")

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(page)

    results = [
        {"id": pp.id, "text": f"{pp.product.name} ({pp.product.code})"}
        for pp in page_obj
    ]
    return JsonResponse({"results": results, "pagination": {"more": page_obj.has_next()}})


def components_autocomplete(request):
    """
    Return plant-scoped NON-FG components for autocomplete dropdown.
    Query params: ?q=term&page=N&plant_id=123
    """
    term = request.GET.get("q", "").strip()
    page = int(request.GET.get("page", 1))
    plant_id = request.GET.get("plant_id")

    qs = ProductPlant.objects.filter(is_fg=False, active=True)
    if plant_id:
        qs = qs.filter(plant_id=plant_id)

    if term:
        qs = qs.filter(
            Q(product__name__icontains=term) | Q(product__code__icontains=term)
        ).order_by("product__name")

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(page)

    results = [
        {"id": pp.id, "text": f"{pp.product.name} ({pp.product.code})"}
        for pp in page_obj
    ]
    return JsonResponse({"results": results, "pagination": {"more": page_obj.has_next()}})
