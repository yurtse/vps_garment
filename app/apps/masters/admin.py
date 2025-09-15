from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import redirect
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from import_export.admin import ImportExportModelAdmin
from django.contrib.admin import TabularInline
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    Plant, ProductionLine, Worker, Party, UserProfile,
    Product, ProductPlant, BOMHeader, BOMItem
)
from .resources import (
    ProductResource, PartyResource, ProductPlantResource,
    PlantResource, ProductionLineResource, WorkerResource,
    UserResource, UserProfileResource
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
    resource_class = ProductPlantResource
    list_display = ("product", "plant", "code", "standard_cost", "active")
    search_fields = ("product__code", "product__name", "plant__code", "code")
    list_filter = ("plant", "active")
    autocomplete_fields = ("product", "plant")


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


@admin.register(BOMHeader)
class BOMHeaderAdmin(admin.ModelAdmin):
    list_display = ("product_plant", "version", "is_active", "effective_from", "effective_to", "created_by", "created_at", "duplicate_action")
    search_fields = ("product_plant__product__code", "product_plant__product__name", "product_plant__plant__code")
    list_filter = ("product_plant__plant", "is_active")
    inlines = (BOMItemInline,)
    readonly_fields = ("version", "created_by", "created_at")
    actions = ("action_duplicate_selected_boms",)

    fieldsets = (
        (None, {
            "fields": (("product_plant", "version"), ("is_active",), ("effective_from", "effective_to"))
        }),
        ("Costing", {"fields": ("scrap_percent", "overhead_cost")}),
        ("Notes", {"fields": ("notes",)}),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('<int:pk>/duplicate/', self.admin_site.admin_view(self.duplicate_view), name='garment_app_bomheader_duplicate'),
        ]
        return custom + urls

    def duplicate_view(self, request, pk):
        original = BOMHeader.objects.get(pk=pk)
        if not request.user.has_perm('garment_app.add_bomheader'):
            messages.error(request, "Permission denied.")
            return redirect('..')

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
        url = reverse('admin:garment_app_bomheader_duplicate', args=[obj.pk])
        return format_html('<a class="button" href="{}">Duplicate</a>', url)
    duplicate_action.short_description = "Duplicate"

    def action_duplicate_selected_boms(self, request, queryset):
        created = 0
        for bom in queryset:
            if not request.user.has_perm('garment_app.add_bomheader'):
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
        self.message_user(request, f"Created {created} duplicate BOM(s) (inactive).", level=messages.INFO)
    action_duplicate_selected_boms.short_description = "Duplicate selected BOM(s) as new version (inactive)"


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
