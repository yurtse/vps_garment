import csv
import io
from django.contrib import admin, messages
from django import forms
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import redirect
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.template.response import TemplateResponse
from django.http import HttpResponseForbidden, HttpResponseRedirect, HttpResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.csrf import csrf_protect
from django.utils.translation import gettext as _
from django.utils.decorators import method_decorator
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from import_export.admin import ImportExportModelAdmin
from django.contrib.admin import TabularInline
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

try:
    from .admin_mixins import PaginationMixin  # your project may have this
except Exception:
    # fallback if your project defines it elsewhere; keep class signature intact
    class PaginationMixin:
        pass

from .models import (
    Plant, ProductionLine, Worker, Party, UserProfile,
    Product, ProductPlant, BOMHeader, BOMItem
)
from .resources import (
    ProductResource, PartyResource, ProductPlantResource,
    PlantResource, ProductionLineResource, WorkerResource,
    UserResource, UserProfileResource
)
from .services.productplant_seed import (
    get_products_missing_for_plant,
    get_products_missing_for_plants,
    seed_productplants,
)

admin.site.site_header = "RFCLabs Admin"     # shown at top of admin pages
admin.site.site_title = "RFCLabs Home"  # shown in browser tab title
admin.site.index_title = "GarmentPro Admin"

User = get_user_model()

# ---------------------
# Pagination mixin (centralized control)
# ---------------------
class PaginationMixin:
    list_per_page = 20


# Plant admin (import/export)
@admin.register(Plant)
class PlantAdmin(PaginationMixin, ImportExportModelAdmin):
    resource_class = PlantResource
    list_display = ("code", "name", "active")
    search_fields = ("code", "name")
    list_filter = ("active",)


@admin.register(ProductionLine)
class ProductionLineAdmin(PaginationMixin, ImportExportModelAdmin):
    resource_class = ProductionLineResource
    list_display = ("code", "name", "plant", "active")
    list_filter = ("plant", "active")
    search_fields = ("code", "name")


@admin.register(Worker)
class WorkerAdmin(PaginationMixin, ImportExportModelAdmin):
    resource_class = WorkerResource
    list_display = ("code", "name", "plant", "production_line", "active")
    list_filter = ("plant", "production_line", "active")
    search_fields = ("code", "name")


@admin.register(Party)
class PartyAdmin(PaginationMixin, ImportExportModelAdmin):
    resource_class = PartyResource
    list_display = ("party_code", "name", "roles_display", "active")
    search_fields = ("party_code", "name", "tax_id")
    list_filter = ("is_vendor", "is_customer", "active")

    def roles_display(self, obj):
        roles = []
        if obj.is_vendor:
            roles.append("Vendor")
        if obj.is_customer:
            roles.append("Customer")
        return ", ".join(roles)
    roles_display.short_description = "Roles"


# UserProfileForm first
class UserProfileForm(forms.ModelForm):
    username = forms.CharField(required=True, max_length=150, help_text="Username for linked User")
    email = forms.EmailField(required=False)
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)
    is_staff = forms.BooleanField(required=False, initial=False)
    is_superuser = forms.BooleanField(required=False, initial=False)
    is_active = forms.BooleanField(required=False, initial=True)
    password = forms.CharField(required=False, widget=forms.PasswordInput, help_text="Optional plaintext password; will be hashed.")

    class Meta:
        model = UserProfile
        fields = ("username", "email", "first_name", "last_name", "is_staff", "is_superuser", "is_active", "password", "plant", "is_plant_admin")

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if not username:
            raise ValidationError("username is required")
        return username

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get("instance")
        if instance and getattr(instance, "user", None):
            u = instance.user
            # only set initial if form not bound (avoids overwriting POST)
            if not self.is_bound:
                self.fields["username"].initial = u.username
                self.fields["email"].initial = u.email
                self.fields["first_name"].initial = u.first_name
                self.fields["last_name"].initial = u.last_name
                self.fields["is_staff"].initial = u.is_staff
                self.fields["is_superuser"].initial = u.is_superuser
                self.fields["is_active"].initial = u.is_active

@admin.register(UserProfile)
class UserProfileAdmin(PaginationMixin, ImportExportModelAdmin):
    resource_class = UserProfileResource
    form = UserProfileForm
    list_display = ("username_display", "full_name", "plant_admin_display", "active_display", "plant")
    search_fields = ("user__username", "user__first_name", "user__last_name", "plant__code")
    list_filter = ("is_plant_admin", "user__is_active", "plant")
    ordering = ("user__username",)

    def username_display(self, obj):
        return obj.user.username if obj.user else ""
    username_display.short_description = "Username"
    username_display.admin_order_field = "user__username"

    def full_name(self, obj):
        if obj.user:
            fn = (obj.user.first_name or "").strip()
            ln = (obj.user.last_name or "").strip()
            name = (fn + " " + ln).strip()
            return name or obj.user.username
        return ""
    full_name.short_description = "Name"
    full_name.admin_order_field = "user__first_name"

    def plant_admin_display(self, obj):
        return bool(obj.is_plant_admin)
    plant_admin_display.boolean = True
    plant_admin_display.short_description = "Plant Admin"
    plant_admin_display.admin_order_field = "is_plant_admin"

    def active_display(self, obj):
        return bool(obj.user.is_active) if obj.user else False
    active_display.boolean = True
    active_display.short_description = "Active"
    active_display.admin_order_field = "user__is_active"

    # keep existing save_model behaviour (ensure it's present in file)
    def save_model(self, request, obj, form, change):
        cd = form.cleaned_data

        setattr(obj, "_username", cd.get("username"))
        setattr(obj, "_email", cd.get("email"))
        setattr(obj, "_first_name", cd.get("first_name"))
        setattr(obj, "_last_name", cd.get("last_name"))
        setattr(obj, "_is_staff", bool(cd.get("is_staff")))
        setattr(obj, "_is_superuser", bool(cd.get("is_superuser")))
        setattr(obj, "_is_active", bool(cd.get("is_active")))
        pwd = cd.get("password")
        if pwd:
            setattr(obj, "_password_plain", pwd)

        setattr(obj, "_update_origin", "profile_admin")
        setattr(obj, "_updated_at", timezone.now())

        username = cd.get("username")
        if not username:
            raise ValidationError("Username is required to create UserProfile.")

        with transaction.atomic():
            user = User.objects.filter(username__iexact=username).first()
            if not user:
                user = User(username=username)
            user.email = cd.get("email") or ""
            user.first_name = cd.get("first_name") or ""
            user.last_name = cd.get("last_name") or ""
            user.is_staff = bool(cd.get("is_staff"))
            user.is_superuser = bool(cd.get("is_superuser"))
            user.is_active = bool(cd.get("is_active", True))
            if pwd:
                user.set_password(pwd)
            elif not user.pk:
                user.set_unusable_password()
            user.save()

            obj.user = user
            super().save_model(request, obj, form, change)

@admin.register(Product)
class ProductAdmin(PaginationMixin, ImportExportModelAdmin):
    resource_class = ProductResource
    list_display = ("code", "name", "shade", "size", "product_group", "style_group", "uom", "active", "standard_cost")
    search_fields = ("code", "name", "product_group", "style_group")
    list_filter = ("active", "product_group", "style_group")
    ordering = ("code",)


@admin.register(ProductPlant)
class ProductPlantAdmin(PaginationMixin, ImportExportModelAdmin):
    """
    ProductPlant admin:
      - preserves PaginationMixin and ImportExportModelAdmin behavior
      - shows joined product fields (via list_select_related)
      - adds a seed-records admin URL (GET-only skeleton)
    """

    resource_class = ProductPlantResource

    # Keep your existing fields and add joined product columns
    list_display = (
        "product_code",   # joined product.code (callable)
        "product_name",   # joined product.name (callable)
        "plant",
        "code",           # ProductPlant.code (plant-specific override)
        "standard_cost",
        "active",
    )

    # Ensure we join product (and plant) to avoid N+1
    list_select_related = ("product", "plant")

    # Keep your search & filters & autocompletes unchanged
    search_fields = ("product__code", "product__name", "plant__code", "code")
    list_filter = ("plant", "active")
    autocomplete_fields = ("product", "plant")

    # Use ImportExportModelAdmin pagination setting if present
    # (PaginationMixin should define list_per_page, otherwise ImportExportModelAdmin default used)

    # ------------------ Callables for joined Product columns ------------------
    def _get_product_attr(self, obj, attr_name, fallback=""):
        prod = getattr(obj, "product", None)
        if prod is not None:
            return getattr(prod, attr_name, fallback)
        # fallback if denormalized product_... field exists on ProductPlant
        return getattr(obj, f"product_{attr_name}", fallback)

    def product_code(self, obj):
        return self._get_product_attr(obj, "code")
    product_code.short_description = "Product Code"
    product_code.admin_order_field = "product__code"

    def product_name(self, obj):
        return self._get_product_attr(obj, "name")
    product_name.short_description = "Product Name"
    product_name.admin_order_field = "product__name"

    # ------------------ Custom admin URL(s) ------------------
    def get_urls(self):
        urls = super().get_urls()
        # register both hyphen and underscore variants to avoid accidental user typing or bookmark mismatch
        custom_urls = [
            path(
                "seed-records/",
                self.admin_site.admin_view(self.seed_records_view),
                name="masters_productplant_seed",
            ),
            path(
                "seed_records/",
                self.admin_site.admin_view(self.seed_records_view),
                # we intentionally give the same name — reverse() will produce the first match
                name="masters_productplant_seed_underscore",
            ),
        ]
        # Put custom URLs *before* default admin urls so they are matched first
        return custom_urls + urls
        
    # ------------------ Seed Records view (GET skeleton) ------------------
    @method_decorator(csrf_protect)
    def seed_records_view(self, request):
        """
        Full GET + POST handler for Seed Records admin page.

        GET:
          - show products missing for a selected plant (superuser chooses plant via ?plant=)
          - apply filters & paginate
        POST:
          - read selected_pks[] or select_all flag
          - validate plant presence
          - call seed_productplants(products, [plant], created_by=request.user)
          - on success: either return CSV download or redirect to ProductPlant changelist with a success message
        """
        # Permission check
        if not self.has_add_permission(request):
            return HttpResponseForbidden("You do not have permission to seed ProductPlant records.")

        context = dict(self.admin_site.each_context(request))
        context.update({"title": "Seed ProductPlant records", "opts": self.model._meta})

        # --- Resolve selected_plant ---
        selected_plant = None
        if request.user.is_superuser:
            context["is_superuser"] = True
            context["plants"] = Plant.objects.all()
            plant_pk = request.GET.get("plant") or request.POST.get("plant")
            if plant_pk:
                try:
                    selected_plant = Plant.objects.get(pk=plant_pk)
                except Plant.DoesNotExist:
                    messages.error(request, "Selected plant not found.")
                    selected_plant = None
        else:
            context["is_superuser"] = False

            # --- robust user profile lookup (works with .profile, .userprofile, and manager-like relations) ---
            userprofile = None
            for attr in ("userprofile", "profile"):
                userprofile = getattr(request.user, attr, None)
                if userprofile is not None:
                    break

            # If the attribute is a manager / RelatedManager, try to get the first related instance
            try:
                from django.db.models import Manager
                if isinstance(userprofile, Manager):
                    userprofile = userprofile.first()
            except Exception:
                # ignore and treat as single-object relationship
                pass

            selected_plant = None
            if userprofile is not None:
                selected_plant = getattr(userprofile, "plant", None)

            if selected_plant is None:
                messages.error(request, "Plant not defined for this user.")
                # Redirect to changelist; return immediately (always return HttpResponse)
                return HttpResponseRedirect(reverse("admin:masters_productplant_changelist"))

        context["selected_plant"] = selected_plant

        # --- Build base product queryset (missing ProductPlant for selected_plant) ---
        products_qs = None
        if selected_plant:
            products_qs = get_products_missing_for_plant(selected_plant)

            # Apply GET filters: q, product_group, style_group, uom, active
            q = request.GET.get("q", "").strip()
            if q:
                products_qs = products_qs.filter(Q(code__icontains=q) | Q(name__icontains=q))

            product_group = request.GET.get("product_group")
            style_group = request.GET.get("style_group")
            uom = request.GET.get("uom")
            active = request.GET.get("active")

            if product_group:
                products_qs = products_qs.filter(product_group=product_group)
            if style_group:
                products_qs = products_qs.filter(style_group=style_group)
            if uom:
                products_qs = products_qs.filter(uom=uom)
            if active in ("true", "True", "1"):
                products_qs = products_qs.filter(active=True)
            elif active in ("false", "False", "0"):
                products_qs = products_qs.filter(active=False)

            # Add distinct filter lists for template
            context["filter_product_groups"] = Product.objects.order_by("product_group").values_list("product_group", flat=True).distinct()
            context["filter_style_groups"] = Product.objects.order_by("style_group").values_list("style_group", flat=True).distinct()
            context["filter_uoms"] = Product.objects.order_by("uom").values_list("uom", flat=True).distinct()

        # ---------- Handle POST: perform seeding ----------
        if request.method == "POST":
            # gather selected product PKs (list) and select_all flag
            selected_pks = request.POST.getlist("selected_pks")
            select_all_flag = request.POST.get("select_all") == "1" or request.POST.get("select_all_matching") == "1"

            # Validate plant presence
            if selected_plant is None:
                messages.error(request, "Plant not defined for this user or not selected.")
                return HttpResponseRedirect(reverse("admin:masters_productplant_changelist"))

            # Determine products to seed
            if select_all_flag:
                # If products_qs is None (unexpected), treat as empty
                if products_qs is None:
                    products_to_seed = []
                else:
                    products_to_seed = list(products_qs)  # evaluate queryset
            else:
                # Convert selected_pks to ints safely
                try:
                    pks_int = [int(x) for x in selected_pks]
                except Exception:
                    pks_int = []
                products_to_seed = list(Product.objects.filter(pk__in=pks_int))

            if not products_to_seed:
                messages.error(request, "No products selected to seed.")
                # Redirect back to the same page preserving plant param
                redirect_url = request.path + (f"?plant={selected_plant.pk}" if selected_plant else "")
                return HttpResponseRedirect(redirect_url)

            # Perform the seed operation inside transaction.atomic
            try:
                with transaction.atomic():
                    summary = seed_productplants(products_to_seed, [selected_plant], created_by=request.user)
            except Exception as exc:
                # Capture and show error, do not return None
                messages.error(request, f"Seeding failed: {exc}")
                redirect_url = request.path + (f"?plant={selected_plant.pk}" if selected_plant else "")
                return HttpResponseRedirect(redirect_url)

            # If user requested CSV download (download=1) return CSV attachment
            if request.POST.get("download") == "1":
                # produce a small CSV with per-product detail if available; otherwise per-plant summary
                csv_buffer = io.StringIO()
                writer = csv.writer(csv_buffer)
                # Header
                writer.writerow(["plant_id", "plant_name", "created", "skipped", "failed"])
                for pid, plant_summary in summary.get("plants", {}).items():
                    writer.writerow([
                        plant_summary.get("plant_id"),
                        plant_summary.get("plant_name"),
                        plant_summary.get("created"),
                        plant_summary.get("skipped"),
                        plant_summary.get("failed"),
                    ])
                csv_value = csv_buffer.getvalue()
                csv_buffer.close()
                resp = HttpResponse(csv_value, content_type="text/csv")
                resp["Content-Disposition"] = f'attachment; filename="productplant_seed_report_plant_{selected_plant.pk}.csv"'
                return resp

            # Otherwise set a success message and redirect to ProductPlant changelist filtered to plant
            created_total = sum(p["created"] for p in summary.get("plants", {}).values())
            skipped_total = sum(p["skipped"] for p in summary.get("plants", {}).values())
            failed_total = sum(p["failed"] for p in summary.get("plants", {}).values())
            messages.success(request, f"Seeding complete — created {created_total}, skipped {skipped_total}, failed {failed_total}")

            # Redirect to changelist filtered by plant (adjust query param to your admin filter if needed)
            changelist_url = reverse("admin:masters_productplant_changelist") + f"?plant__id__exact={selected_plant.pk}"
            return HttpResponseRedirect(changelist_url)

        # ---------- GET: paginate and render template ----------
        # Setup pagination only if we have a products_qs (i.e. plant selected)
        if products_qs is not None:
            per_page = getattr(self, "list_per_page", 100)
            paginator = Paginator(products_qs, per_page)
            page_num = request.GET.get("page", 1)
            try:
                products_page = paginator.page(page_num)
            except PageNotAnInteger:
                products_page = paginator.page(1)
            except EmptyPage:
                products_page = paginator.page(paginator.num_pages)

            context.update({
                "products_qs": products_qs,
                "products_page": products_page,
                "paginator": paginator,
                "products_count": products_qs.count(),
                "q": request.GET.get("q", "").strip(),
                "applied_filters": {
                    "product_group": request.GET.get("product_group", "") or "",
                    "style_group": request.GET.get("style_group", "") or "",
                    "uom": request.GET.get("uom", "") or "",
                    "active": request.GET.get("active", "") or "",
                },
            })
        else:
            context.update({
                "products_qs": None,
                "products_page": None,
                "paginator": None,
                "products_count": 0,
                "q": "",
                "applied_filters": {},
            })

        # Always return a TemplateResponse for GET
        return TemplateResponse(request, "admin/masters/productplant/seed_records.html", context)

    def _get_user_profile_plant(self, request):
        # reuse the robust lookup from seed_records_view
        userprofile = None
        for attr in ("userprofile", "profile"):
            userprofile = getattr(request.user, attr, None)
            if userprofile is not None:
                break
        # if it's a manager/related manager, get first()
        try:
            from django.db.models import Manager
            if isinstance(userprofile, Manager):
                userprofile = userprofile.first()
        except Exception:
            pass
        return getattr(userprofile, "plant", None) if userprofile is not None else None

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Keep superuser behavior unchanged
        if request.user.is_superuser:
            return qs.select_related("product", "plant")
        # For other users, scope to their assigned plant
        plant = self._get_user_profile_plant(request)
        if plant is None:
            # Return empty queryset for users with no plant assigned
            return qs.none()
        return qs.filter(plant=plant).select_related("product", "plant")

    def get_list_filter(self, request):
        """
        Show the plant filter only to superusers (non-superusers already scoped via get_queryset).
        Keep other filters for everyone.
        """
        base_filters = ("active",)  # keep active always
        # keep product-group/style filters if you had them; here I'm showing a minimal example
        if request.user.is_superuser:
            # include plant filter for superusers
            return ("plant",) + base_filters
        return base_filters

    def changelist_view(self, request, extra_context=None):
        """
        Inject seed_link_for_plant into changelist context.
        - For plant-scoped users: direct link to seed page for their plant (with ?plant=)
        - For superusers: link to seed page (no plant param) so they can pick plants
        """
        extra_context = dict(extra_context or {})
        plant = self._get_user_profile_plant(request)

        if plant:
            # direct link for scoped users
            seed_url = reverse("admin:masters_productplant_seed") + f"?plant={plant.pk}"
        else:
            # show a generic seed page link for superusers (or other users with add permission)
            seed_url = reverse("admin:masters_productplant_seed")

        # Only show link if user can add ProductPlant (keep permission check)
        if self.has_add_permission(request):
            extra_context["seed_link_for_plant"] = seed_url
        else:
            extra_context["seed_link_for_plant"] = None

        # Call the original changelist view and attempt to ensure the link is visible
        resp = super().changelist_view(request, extra_context=extra_context)

        # If TemplateResponse, try to inject snippet if it wasn't rendered by template (keeps previous behavior)
        try:
            if isinstance(resp, TemplateResponse):
                resp.render()
                content = resp.content.decode(errors="ignore")
                if extra_context.get("seed_link_for_plant") and "Seed missing products" not in content:
                    snippet = (
                        f'<div class="seed-link-wrapper" style="margin: .5rem 0;">'
                        f'<a href="{extra_context["seed_link_for_plant"]}" class="button addlink" '
                        f'style="display:inline-block; padding:6px 10px;">Seed missing products</a>'
                        f'<span style="margin-left:.6rem; color:#666;">'
                        f'Create ProductPlant rows for products missing in your plant.'
                        f'</span></div>'
                    )
                    insert_at = content.find('<div id="content-main">')
                    if insert_at != -1:
                        insert_at = content.find('>', insert_at) + 1
                    else:
                        insert_at = content.find('<body')
                        if insert_at != -1:
                            insert_at = content.find('>', insert_at) + 1
                        else:
                            insert_at = 0
                    new_content = content[:insert_at] + snippet + content[insert_at:]
                    resp.content = new_content.encode()
        except Exception:
            pass

        return resp

# BOM admin
class BOMItemInline(TabularInline):
    model = BOMItem
    extra = 1
    fields = ("component", "quantity", "uom_display")
    readonly_fields = ("uom_display",)
    autocomplete_fields = ("component",)

    def uom_display(self, obj):
        return obj.component.product.uom if obj and obj.component else ""
    uom_display.short_description = "UOM"

class BOMHeaderAdmin(admin.ModelAdmin):
    list_display = (
        "product_plant",
        "version",
        "workflow_state",
        "effective_from",
        "effective_to",
        "approved_by",
        "approved_at",
        "created_at",
        "duplicate_action",
    )
    search_fields = (
        "product_plant__product__code",
        "product_plant__product__name",
        "product_plant__plant__code",
    )
    list_filter = ("product_plant__plant", "workflow_state")
    inlines = (BOMItemInline,)
    readonly_fields = (
        "version",
        "workflow_state",
        "approved_by",
        "approved_at",
        "total_cost_snapshot",
        "immutable_snapshot",
        "created_at",
        "updated_at",
    )
    actions = ("action_duplicate_selected_boms", "action_approve_selected_boms")

    fieldsets = (
        (None, {
            "fields": (
                ("product_plant", "version"),
                ("workflow_state",),
                ("effective_from", "effective_to"),
            )
        }),
        ("Costing / Snapshots", {
            "fields": ("total_cost_snapshot", "immutable_snapshot"),
        }),
        ("Approval / Audit", {
            "fields": ("approved_by", "approved_at"),
        }),
    )


    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    # ---------------- Custom admin actions / urls ----------------

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:pk>/duplicate/",
                self.admin_site.admin_view(self.duplicate_view),
                name="garment_app_bomheader_duplicate",
            ),
        ]
        return custom + urls

    def duplicate_view(self, request, pk):
        original = BOMHeader.objects.get(pk=pk)
        if not request.user.has_perm("garment_app.add_bomheader"):
            messages.error(request, "Permission denied.")
            return redirect("..")

        with transaction.atomic():
            new = BOMHeader.objects.create(
                product_plant=original.product_plant,
                is_active=False,
                effective_from=original.effective_from,
                effective_to=original.effective_to,
                scrap_percent=original.scrap_percent,
                overhead_cost=original.overhead_cost,
                notes=f"Duplicated from v{original.version}: {original.notes or ''}",
                created_by=request.user,
            )
            for it in original.items.all():
                new.items.create(component=it.component, quantity=it.quantity)
        messages.success(request, f"Duplicated BOM created: {new}")
        return redirect(f"../{new.pk}/change/")

    def duplicate_action(self, obj):
        url = reverse("admin:garment_app_bomheader_duplicate", args=[obj.pk])
        return format_html('<a class="button" href="{}">Duplicate</a>', url)

    duplicate_action.short_description = "Duplicate"

    def action_duplicate_selected_boms(self, request, queryset):
        created = 0
        for bom in queryset:
            if not request.user.has_perm("garment_app.add_bomheader"):
                continue
            with transaction.atomic():
                new = BOMHeader.objects.create(
                    product_plant=bom.product_plant,
                    is_active=False,
                    effective_from=bom.effective_from,
                    effective_to=bom.effective_to,
                    scrap_percent=bom.scrap_percent,
                    overhead_cost=bom.overhead_cost,
                    notes=f"Duplicated from v{bom.version}: {bom.notes or ''}",
                    created_by=request.user,
                )
                for it in bom.items.all():
                    new.items.create(component=it.component, quantity=it.quantity)
                created += 1
        self.message_user(
            request, f"Created {created} duplicate BOM(s) (inactive).", level=messages.INFO
        )

    action_duplicate_selected_boms.short_description = "Duplicate selected BOM(s) as new version (inactive)"

    # ---------------- Approve action & helpers ----------------

    @admin.action(description="Approve selected BOM(s)")
    def action_approve_selected_boms(self, request, queryset):
        success = 0
        for bom in queryset:
            # permission check
            if not request.user.has_perm("garment_app.change_bomheader"):
                self.message_user(request, f"No permission to approve BOM id={bom.pk}", level=messages.WARNING)
                continue
            try:
                # If you have a helper to compute total cost, call it here:
                # total_cost = compute_bom_total_cost(bom)
                total_cost = None
                bom.approve(user=request.user, total_cost=total_cost)
                success += 1
            except Exception as exc:
                self.message_user(
                    request, f"Failed to approve BOM id={bom.pk}: {exc}", level=messages.ERROR
                )
        self.message_user(request, _("Approved %d BOM(s).") % success)

    action_approve_selected_boms.short_description = "Approve selected BOM(s)"

# register or re-register
try:
    admin.site.unregister(BOMHeader)
except Exception:
    pass
admin.site.register(BOMHeader, BOMHeaderAdmin)


# Safe User admin override
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

class CustomUserAdmin(PaginationMixin, DjangoUserAdmin):
    def save_model(self, request, obj, form, change):
        setattr(obj, "_update_origin", "user_ui")
        setattr(obj, "_updated_at", timezone.now())
        super().save_model(request, obj, form, change)

admin.site.register(User, CustomUserAdmin)
