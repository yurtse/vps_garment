# garment_app/models.py
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Max
from django.utils.translation import gettext_lazy as _

User = settings.AUTH_USER_MODEL


class ProductGroup(models.TextChoices):
    FINISHED_GOOD = "FG", "Finished Good"
    RAW_MATERIAL = "RM", "Raw Material"
    WIP = "WIP", "Work in Progress"


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
    shade = models.CharField(max_length=60, blank=True, default="")
    size = models.CharField(max_length=30, blank=True, default="")
    uom = models.CharField(max_length=20, blank=True, default="pcs")
    standard_cost = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0.0"))
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Product"
        verbose_name_plural = "Products"

    def __str__(self):
        return f"{self.code} - {self.name}"


class ProductPlant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="product_plants")
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="product_plants")
    code = models.CharField(max_length=64, blank=True, null=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    active = models.BooleanField(default=True)
    standard_cost = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0.0"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("product", "plant")
        ordering = ("product__code", "plant__code")
        verbose_name = "Product (Plant)"
        verbose_name_plural = "Products (Plant)"

    def __str__(self):
        return f"{self.product.code}@{self.plant.code}"

    @classmethod
    def get_or_inherit(cls, product: Product, plant: Plant, create_if_missing: bool = True) -> "ProductPlant":
        try:
            return cls.objects.get(product=product, plant=plant)
        except cls.DoesNotExist:
            if not create_if_missing:
                raise
            pp = cls.objects.create(
                product=product,
                plant=plant,
                code=product.code,
                name=product.name,
                active=product.active,
                standard_cost=Decimal("0.0"),
            )
            return pp

    def get_effective_standard_cost(self):
        """
        Return plant-level standard cost when present (>0), otherwise fallback to product.standard_cost.
        """
        if self.standard_cost and self.standard_cost > 0:
            return self.standard_cost
        return self.product.standard_cost


class BOMHeader(models.Model):
    """
    BOM tied to a ProductPlant (Finished Good at a specific Plant).
    Version auto-increments per product_plant; only one active BOM allowed per product_plant.
    """
    product_plant = models.ForeignKey(
        ProductPlant,
        on_delete=models.CASCADE,
        related_name="boms",
        help_text="Finished Good (plant-specific)"
    )
    version = models.PositiveIntegerField(default=1, editable=False)
    effective_from = models.DateField(blank=True, null=True)
    effective_to = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    scrap_percent = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.0"))
    overhead_cost = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0.0"))
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("product_plant__product__code", "product_plant__plant__code", "-version")
        unique_together = (("product_plant", "version"),)
        verbose_name = "BOM"
        verbose_name_plural = "BOMs"

    def clean(self):
        # product_plant.product must be FG
        if self.product_plant and self.product_plant.product.product_group != ProductGroup.FINISHED_GOOD:
            raise ValidationError({"product_plant": _("Selected product must be a Finished Good (FG).")})
        if self.effective_from and self.effective_to and self.effective_from > self.effective_to:
            raise ValidationError({"effective_to": _("Effective to must be after Effective from.")})

    def save(self, *args, **kwargs):
        is_create = self._state.adding
        with transaction.atomic():
            if is_create:
                last = BOMHeader.objects.filter(product_plant=self.product_plant).aggregate(m=Max("version"))["m"]
                self.version = 1 if not last else (last + 1)
            super().save(*args, **kwargs)
            # Enforce single active BOM per product_plant
            if self.is_active:
                BOMHeader.objects.filter(product_plant=self.product_plant).exclude(pk=self.pk).update(is_active=False)

    def compute_total_cost(self):
        """
        Compute BOM cost using ProductPlant.get_effective_standard_cost() for components.
        Total = sum(component_qty * component_cost) + overhead_cost
        """
        total = Decimal("0.0")
        for item in self.items.all():
            # item.component is a ProductPlant
            cost = item.component.get_effective_standard_cost()
            qty = Decimal(item.quantity or 0)
            total += qty * Decimal(cost or Decimal("0.0"))
        total += Decimal(self.overhead_cost or Decimal("0.0"))
        return total

    def __str__(self):
        return f"BOM {self.product_plant.product.code} @ {self.product_plant.plant.code} v{self.version}"


class BOMItem(models.Model):
    """
    Component is a ProductPlant (plant-scoped component).
    Validate that component.plant == bom.product_plant.plant.
    """
    bom = models.ForeignKey(BOMHeader, related_name="items", on_delete=models.CASCADE)
    component = models.ForeignKey(
        ProductPlant,
        on_delete=models.PROTECT,
        related_name="bom_components",
        help_text="Component as plant-specific product (ProductPlant)"
    )
    quantity = models.DecimalField(max_digits=10, decimal_places=4)

    class Meta:
        unique_together = ("bom", "component")
        ordering = ("id",)
        verbose_name = "BOM Item"

    def clean(self):
        # component must be active
        if not self.component.active:
            raise ValidationError({"component": _("Component product must be active.")})

        # component must belong to same plant as BOM.product_plant
        if self.bom and self.component.plant_id != self.bom.product_plant.plant_id:
            raise ValidationError({"component": _("Component must belong to same plant as BOM's finished good.")})

        # component product should not be FG (prevent using finished goods as raw components)
        if self.component.product.product_group == ProductGroup.FINISHED_GOOD:
            raise ValidationError({"component": _("Component cannot be a Finished Good (FG).")})

    def __str__(self):
        return f"{self.component.product.code}@{self.component.plant.code} x {self.quantity}"
