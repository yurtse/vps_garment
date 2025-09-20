# /code/apps/masters/views.py
"""
Autocomplete endpoints used by the admin JS for BOM header (FG) and
BOM item component pickers.

Endpoints (mounted under /masters/ in project urls):
- GET /masters/api/autocomplete/fg/?q=...&page=1&plant_id=...
- GET /masters/api/autocomplete/components/?q=...&page=1&plant_id=...

Response format (JSON):
{
  "results": [{"id": <productplant_id>, "text": "Name | Shade | Size"}...],
  "pagination": {"more": false}
}

Notes / changes implemented:
- _format_result builds the display text as "name | shade | size" and falls
  back to ProductPlant.name or Product.code if product fields missing.
- Uses plant scoping: ?plant_id=, then user-profile if not superuser.
- Keeps queries index-friendly: filters by is_fg + plant_id (if provided).
- Defensive: handles pagination edge cases and returns consistent structure.
"""

from typing import Tuple, Optional

from django.http import JsonResponse, HttpRequest
from django.db.models import Q
from django.core.paginator import Paginator
from django.views.decorators.http import require_GET

from .models import ProductPlant

PAGE_SIZE = 20


def _get_plant_for_request(request: HttpRequest) -> Optional[int]:
    """
    Resolve plant id for request:
    - If ?plant_id= provided, honor it (best-effort int conversion).
    - Else, if user has a userprofile with plant_id, use that (for non-superusers).
    - Else None (means no plant filter; superuser sees all).
    """
    plant_id = request.GET.get("plant_id")
    if plant_id:
        try:
            return int(plant_id)
        except (TypeError, ValueError):
            return None

    user = getattr(request, "user", None)
    if user and not getattr(user, "is_superuser", False):
        # Best-effort profile access: user.userprofile or user.profile
        profile = getattr(user, "userprofile", None) or getattr(user, "profile", None)
        if profile:
            return getattr(profile, "plant_id", None)
    return None


def _format_result(pp: ProductPlant) -> str:
    """
    Format display text for ProductPlant as "name | shade | size".
    - Prefer product fields (product.name, product.shade, product.size).
    - Fall back to ProductPlant.name or ProductPlant.code if product missing.
    - Trim and omit empty parts.
    """
    prod = getattr(pp, "product", None)
    # prefer product.name when present, else productplant.name
    name = ""
    if prod:
        name = (getattr(prod, "name", "") or "").strip()
    if not name:
        name = (pp.name or "").strip()
    shade = (getattr(prod, "shade", "") or "").strip() if prod else ""
    size = (getattr(prod, "size", "") or "").strip() if prod else ""

    parts = [p for p in (name, shade, size) if p]
    if parts:
        return " | ".join(parts)
    # final fallback to code
    return (pp.code or "").strip()


def _search_productplants(q: str, plant_id: Optional[int], is_fg: bool, page: int) -> Tuple[list, bool]:
    """
    Query ProductPlant rows filtered by plant_id (if provided) and is_fg flag.
    Search across ProductPlant.name, Product.shade and Product.size and ProductPlant.code.
    Returns (results_list, more_flag).

    Important: the DB should have composite index on (plant_id, is_fg) so the initial
    filter is index-only before the ILIKE/WHERE clause narrows results.
    """
    qs = ProductPlant.objects.select_related("product").filter(is_fg=is_fg, active=True)
    if plant_id:
        qs = qs.filter(plant_id=plant_id)

    if q:
        q_term = q.strip()
        # keep queries simple and sargable; the ORM builds them as ILIKE on fields
        qs = qs.filter(
            Q(name__icontains=q_term)
            | Q(code__icontains=q_term)
            | Q(product__name__icontains=q_term)
            | Q(product__shade__icontains=q_term)
            | Q(product__size__icontains=q_term)
        )

    qs = qs.order_by("name", "id")
    paginator = Paginator(qs, PAGE_SIZE)
    try:
        page_obj = paginator.page(page)
    except Exception:
        # page out of range -> return first page if any
        page_obj = paginator.page(1) if paginator.num_pages else []

    results = []
    # Format each ProductPlant into the {id, text} shape expected by the client
    for pp in page_obj:
        results.append({"id": pp.id, "text": _format_result(pp)})

    more = page_obj.has_next() if hasattr(page_obj, "has_next") else False
    return results, more


@require_GET
def fg_autocomplete(request: HttpRequest) -> JsonResponse:
    """
    Autocomplete for Finished Goods (FG) ProductPlant rows.
    Returns JSON structure consumed by admin JS.
    """
    q = request.GET.get("q", "") or ""
    try:
        page = int(request.GET.get("page", "1") or 1)
    except (TypeError, ValueError):
        page = 1
    plant_id = _get_plant_for_request(request)
    results, more = _search_productplants(q=q, plant_id=plant_id, is_fg=True, page=page)
    return JsonResponse({"results": results, "pagination": {"more": more}})


@require_GET
def components_autocomplete(request: HttpRequest) -> JsonResponse:
    """
    Autocomplete for component ProductPlant rows (not FG).
    """
    q = request.GET.get("q", "") or ""
    try:
        page = int(request.GET.get("page", "1") or 1)
    except (TypeError, ValueError):
        page = 1
    plant_id = _get_plant_for_request(request)
    results, more = _search_productplants(q=q, plant_id=plant_id, is_fg=False, page=page)
    return JsonResponse({"results": results, "pagination": {"more": more}})
