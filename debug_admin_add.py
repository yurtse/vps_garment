# debug_admin_add.py
import traceback
from django.test import RequestFactory
from django.contrib import admin
from django.contrib.auth import get_user_model
from apps.masters.models import BOMHeader

try:
    User = get_user_model()
    su = User.objects.filter(is_superuser=True).first()
    if su is None:
        raise RuntimeError("No superuser found to attach to request.")
    rf = RequestFactory()
    req = rf.get("/admin/apps/masters/bomheader/add/")
    req.user = su
    ma = admin.site._registry.get(BOMHeader)
    if ma is None:
        raise RuntimeError("BOMHeader not registered in admin.")
    try:
        resp = ma.add_view(req)
        print("add_view returned:", type(resp), getattr(resp, "status_code", None))
    except Exception:
        traceback.print_exc()
except Exception:
    traceback.print_exc()
