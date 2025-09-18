# garment_app/models.py
from __future__ import annotations

from decimal import Decimal
from typing import Optional
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Max
from django.utils.translation import gettext_lazy as _

User = settings.AUTH_USER_MODEL

# (Ensure JSONField import matches your Django version)
try:
    from django.db.models import JSONField
except Exception:
    # Django < 3.1 fallback (if using postgres and django.contrib.postgres)
    from django.contrib.postgres.fields import JSONField



class ProductGroup(models.TextChoices):
    FINISHED_GOOD = "FG", "Finished Good"
    RAW_MATERIAL = "RM", "Raw Material"
    WIP = "WIP", "Work in Progress"
    TRIMS1 = "TRM1", "Trims BOM Excl" 
    TRIMS0 = "TRM0", "Trims BOM Incl" 


class Plant(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    address = models.TextField(blank=True, null=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code",)
        verbose_name = "Plant"
        verbose_name_plural = "Plants"

    def __str__(self):
        return f"{self.code} - {self.name}"


class ProductionLine(models.Model):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="production_lines")
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=128)
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ("plant", "code")
        ordering = ("plant__code", "code")
        verbose_name = "Production Line"
        verbose_name_plural = "Production Lines"

    def __str__(self):
        return f"{self.plant.code}/{self.code} - {self.name}"


class Worker(models.Model):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="workers")
    production_line = models.ForeignKey(ProductionLine, on_delete=models.SET_NULL, related_name="workers", null=True, blank=True)
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=128)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("plant", "code")
        ordering = ("plant__code", "code")
        verbose_name = "Worker"

    def __str__(self):
        return f"{self.code} - {self.name} ({self.plant.code})"


class Party(models.Model):
    party_code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True, null=True)
    contact_person = models.CharField(max_length=128, blank=True, null=True)
    contact_number = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    tax_id = models.CharField(max_length=64, blank=True, null=True)
    is_vendor = models.BooleanField(default=False)
    is_customer = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("party_code",)
        verbose_name = "Party"
        verbose_name_plural = "Parties"

    def clean(self):
        if not (self.is_vendor or self.is_customer):
            raise ValidationError(_("Party must be at least vendor or customer."))
        if Party.objects.exclude(pk=self.pk).filter(party_code__iexact=self.party_code).exists():
            raise ValidationError({"party_code": _("Duplicate party code not allowed.")})

    def __str__(self):
        roles = []
        if self.is_vendor:
            roles.append("Vendor")
        if self.is_customer:
            roles.append("Customer")
        role_s = "/".join(roles) if roles else "None"
        return f"{self.party_code} — {self.name} ({role_s})"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    plant = models.ForeignKey(Plant, on_delete=models.SET_NULL, blank=True, null=True, related_name="users")
    is_plant_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Sync/optimistic fields to help avoid loops and allow timestamp checks
    last_synced_to_user = models.DateTimeField(blank=True, null=True, help_text="When profile last pushed changes to User")
    last_synced_from_user = models.DateTimeField(blank=True, null=True, help_text="When profile last pulled changes from User")

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"profile: {self.user} ({self.plant.code if self.plant else 'no-plant'})"


class Product(models.Model):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)
    product_group = models.CharField(
        max_length=10,
        choices=ProductGroup.choices,
        default=ProductGroup.RAW_MATERIAL,
    )
    
    style_group = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Optional: style group / collection"
    )
    
    shade = models.CharField(max_length=60, blank=True, default="")
    size = models.CharField(max_length=30, blank=True, default="")
    uom = models.CharField(max_length=20, blank=True, default="pcs")
    standard_cost = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.0"))
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Product"
        verbose_name_plural = "Products"

    def __str__(self):
        return f"{self.code} - {self.name}"


# rfc_dev/app/apps/masters/models.py
# ---- Replace only the ProductPlant class in your existing models.py with the class below ----
# (keep the rest of models.py unchanged)

class ProductPlant(models.Model):
    """
    Plant-scoped extension of Product. One Product may have multiple ProductPlant records
    (one per plant). This class has been extended (Phase 1) to denormalize product type info
    for faster queries in admin/autocomplete.

    CHANGES (Phase 1):
    - Added `is_fg` boolean (nullable) to indicate if this ProductPlant is a Finished Good (FG).
      Initially nullable so DB migration can add the column without breaking existing code.
    - Added `product_type_code` integer (nullable) to store a small code for product group/type.
      This is optional and can be used in place of textual comparisons for high-performance filters.
    """

    product = models.ForeignKey("Product", on_delete=models.CASCADE, related_name="productplants")
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=256)
    plant = models.ForeignKey("Plant", on_delete=models.PROTECT, related_name="productplants")
    active = models.BooleanField(default=True)

    # ---------- Phase 1 additions (nullable for safe migration) ----------
    # Denormalized flag indicating this productplant is a Finished Good (FG).
    # Backfill migration will set this based on Product.product_group.
    is_fg = models.BooleanField(null=True, blank=True, help_text="Denormalized: is this a Finished Good (FG)?")

    # Optional small integer code representing product group/type (useful for indexed filters).
    # Example mapping (to be used by seed/backfill):
    #   1 => FINISHED_GOOD, 2 => RAW_MATERIAL, 3 => WIP, 4 => TRM
    product_type_code = models.IntegerField(null=True, blank=True, help_text="Small int code for product type/group")

    # --------------------------------------------------------------------

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("product", "plant")
        ordering = ("product__code", "plant__code")
        verbose_name = "Product - Plant"
        verbose_name_plural = "Products - Plants"

        # Ensure Django knows about the composite index so it doesn't attempt to remove it.
        indexes = [
            models.Index(fields=["plant_id", "is_fg"], name="masters_pp_plant_isfg_idx"),
        ]        

    def __str__(self):
        return f"{self.code} - {self.name} @ {self.plant.code}"

    # Convenience helper (non-breaking addition)
    @property
    def is_finished_good(self):
        """
        Return a boolean for older code paths — if is_fg is null we fall back to product.product_group.
        This helps existing code continue to work until we enforce non-null.
        """
        if self.is_fg is not None:
            return bool(self.is_fg)
        # Fallback to product's textual group (safe during migration window)
        try:
            return self.product.product_group == ProductGroup.FINISHED_GOOD
        except Exception:
            return False

    def standard_cost(self):
        """
        Admin-friendly accessor: return the product's standard cost if available.
        This lets admin list_display reference 'standard_cost' on ProductPlant.
        """
        try:
            return getattr(self.product, "standard_cost", None) or Decimal("0.00")
        except Exception:
            return Decimal("0.00")

    # Optional: nice label when shown in admin list display
    standard_cost.fget = getattr(standard_cost, "__call__", None)  # no-op to keep linter quiet
    standard_cost.short_description = "Standard Cost"


class BOMHeader(models.Model):
    product_plant = models.ForeignKey("ProductPlant", on_delete=models.PROTECT, related_name="boms")
    version = models.IntegerField(default=1)

    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)

    # ---- Phase 2 additions (snapshot / workflow / audit) ----
    class WorkflowState(models.TextChoices):
        DRAFT = "DRAFT", _("Draft")
        APPROVED = "APPROVED", _("Approved")
        ACTIVE = "ACTIVE", _("Active")
        ARCHIVED = "ARCHIVED", _("Archived")

    workflow_state = models.CharField(
        max_length=16,
        choices=WorkflowState.choices,
        default=WorkflowState.DRAFT,
        help_text="Governance state of this BOM",
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    total_cost_snapshot = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    immutable_snapshot = JSONField(null=True, blank=True, help_text="Optional read-only snapshot stored on approve/activate")
    # -----------------------------------------------------------

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("product_plant", "version")
        constraints = [
            # ensure unique (product_plant, version) at DB level
            models.UniqueConstraint(fields=["product_plant", "version"], name="masters_bomheader_pp_version_uniq"),
        ]

    def __str__(self):
        return f"BOM {self.product_plant.code} v{self.version}"

    def clean(self):
        # keep your effective-date overlap validation (same as before)...
        if self.effective_from and self.effective_to and self.effective_from > self.effective_to:
            raise ValidationError({"effective_to": _("Effective to must be on or after effective from.")})

        checking_states = {self.WorkflowState.APPROVED, self.WorkflowState.ACTIVE}
        if self.workflow_state not in checking_states:
            return

        qs = BOMHeader.objects.filter(product_plant=self.product_plant).exclude(pk=self.pk).filter(workflow_state__in=list(checking_states))
        for other in qs.select_related("product_plant").iterator():
            other_from = getattr(other, "effective_from", None)
            other_to = getattr(other, "effective_to", None)
            left_ok = (self.effective_from is None) or (other_to is None) or (self.effective_from <= other_to)
            right_ok = (self.effective_to is None) or (other_from is None) or (self.effective_to >= other_from)
            if left_ok and right_ok:
                raise ValidationError(
                    {
                        "effective_from": _(
                            "Effective date range overlaps with another %s BOM (id=%s, version=%s, state=%s)."
                        ) % (self.product_plant.code, other.pk, other.version, other.workflow_state)
                    }
                )

    def approve(self, user=None, total_cost=None, immutable_snapshot=None):
        """
        Transition to APPROVED and persist snapshots.
        """
        now = timezone.now()
        if user:
            self.approved_by = user
        if not self.approved_at:
            self.approved_at = now
        if total_cost is not None:
            self.total_cost_snapshot = total_cost
        if immutable_snapshot is not None:
            self.immutable_snapshot = immutable_snapshot
        else:
            self.immutable_snapshot = {
                "product_plant_id": self.product_plant_id,
                "version": self.version,
                "effective_from": str(self.effective_from) if self.effective_from else None,
                "effective_to": str(self.effective_to) if self.effective_to else None,
            }
        self.workflow_state = self.WorkflowState.APPROVED
        self.save(update_fields=["workflow_state", "approved_by", "approved_at", "total_cost_snapshot", "immutable_snapshot", "updated_at"])

    def activate(self, user=None):
        """
        Mark this BOM as ACTIVE and archive other ACTIVE BOMs for same product_plant.
        Should be wrapped in transaction.atomic() by caller if doing multi-row operations.
        """
        with transaction.atomic():
            BOMHeader.objects.filter(product_plant=self.product_plant, workflow_state=self.WorkflowState.ACTIVE).exclude(pk=self.pk).update(workflow_state=self.WorkflowState.ARCHIVED)
            self.workflow_state = self.WorkflowState.ACTIVE
            if user:
                self.approved_by = user
            if not self.approved_at:
                self.approved_at = timezone.now()
            self.save(update_fields=["workflow_state", "approved_by", "approved_at", "updated_at"])

    @classmethod
    def create_with_next_version(cls, product_plant, **kwargs):
        """
        Concurrency-safe factory to allocate the next version for a given product_plant.

        Serializes allocation by taking a SELECT ... FOR UPDATE lock on the ProductPlant row.
        Usage: with transaction.atomic(): BOMHeader.create_with_next_version(pp, effective_from=..., ...)
        """
        # Import here to avoid circular import if ProductPlant is in same file
        ProductPlant = cls._meta.apps.get_model("masters", "ProductPlant")
        with transaction.atomic():
            # lock the ProductPlant row to serialize concurrent creators
            pp = ProductPlant.objects.select_for_update().get(pk=product_plant.pk if hasattr(product_plant, "pk") else product_plant)
            # get the highest existing version
            last = cls.objects.filter(product_plant=pp).order_by("-version").first()
            next_version = (last.version + 1) if last else 1
            kwargs.setdefault("version", next_version)
            # ensure product_plant is the instance
            kwargs.setdefault("product_plant", pp)
            instance = cls.objects.create(**kwargs)
            return instance

class BOMItem(models.Model):
    bom = models.ForeignKey("BOMHeader", related_name="items", on_delete=models.CASCADE)
    component = models.ForeignKey(
        "ProductPlant",
        on_delete=models.PROTECT,
        related_name="bom_components",
        help_text="Component as plant-specific product (ProductPlant)"
    )
    quantity = models.DecimalField(max_digits=10, decimal_places=2)

    # ---- Phase 2 additions: snapshots ----
    unit_cost_snapshot = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    extended_cost_snapshot = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    # -----------------------------------------------------

    class Meta:
        constraints = [
            # DB-level uniqueness to prevent duplicate component rows per BOM
            models.UniqueConstraint(fields=["bom", "component"], name="masters_bomitem_bom_component_uniq"),
        ]
        ordering = ("id",)
        verbose_name = "BOM Item"

    def clean(self):
        # reuse your existing validations: active, same plant, component not FG
        if not self.component.active:
            raise ValidationError({"component": _("Component product must be active.")})
        if self.bom and self.component.plant_id != self.bom.product_plant.plant_id:
            raise ValidationError({"component": _("Component must belong to same plant as BOM's finished good.")})
        # prevent using finished goods as raw components
        if self.component.product.product_group == ProductGroup.FINISHED_GOOD:
            raise ValidationError({"component": _("Component cannot be a Finished Good (FG).")})

    def __str__(self):
        return f"{self.component.product.code}@{self.component.plant.code} x {self.quantity}"