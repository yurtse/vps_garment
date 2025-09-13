# garment_app/resources.py
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.results import RowResult
from import_export.formats.base_formats import CSV

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_date
from decimal import Decimal

from .models import (
    Plant, Product, ProductPlant, ProductionLine, Worker,
    Party, UserProfile
)

User = get_user_model()


class PlantResource(resources.ModelResource):
    class Meta:
        model = Plant
        import_id_fields = ("code",)
        fields = ("code", "name", "address", "active")
        export_order = ("code", "name", "address", "active")


class ProductResource(resources.ModelResource):
    class Meta:
        model = Product
        import_id_fields = ("code",)
        fields = ("code", "name", "product_group", "shade", "size", "uom", "active", "standard_cost")
        export_order = ("code", "name", "product_group", "shade", "size", "uom", "active", "standard_cost")


class ProductPlantResource(resources.ModelResource):
    product = fields.Field(attribute="product", column_name="product_code",
                           widget=ForeignKeyWidget(Product, "code"))
    plant = fields.Field(attribute="plant", column_name="plant_code",
                         widget=ForeignKeyWidget(Plant, "code"))

    class Meta:
        model = ProductPlant
        import_id_fields = ("product", "plant")
        fields = ("product", "plant", "code", "name", "standard_cost", "active")
        export_order = ("product", "plant", "code", "name", "standard_cost", "active")


class ProductionLineResource(resources.ModelResource):
    plant = fields.Field(attribute="plant", column_name="plant_code",
                         widget=ForeignKeyWidget(Plant, "code"))

    class Meta:
        model = ProductionLine
        import_id_fields = ("plant", "code")
        fields = ("plant", "code", "name", "active", "notes")
        export_order = ("plant", "code", "name", "active", "notes")

    def before_import_row(self, row, **kwargs):
        if "plant_code" not in [k.lower() for k in row.keys()]:
            raise ValidationError("ProductionLine import requires 'plant_code' column.")


class WorkerResource(resources.ModelResource):
    # Accept plant_code and production_line_code in CSV for resolution in before_import_row.
    plant_code = fields.Field(column_name="plant_code")
    production_line_code = fields.Field(column_name="production_line_code")

    # Actual FK fields to be resolved/populated by before_import_row:
    plant = fields.Field(attribute="plant", column_name="plant", widget=ForeignKeyWidget(Plant, "code"))
    production_line = fields.Field(attribute="production_line", column_name="production_line", widget=ForeignKeyWidget(ProductionLine, "code"))

    class Meta:
        model = Worker
        import_id_fields = ("plant", "code")
        # include the CSV helper columns in fields so import_export doesn't warn
        fields = ("plant", "production_line", "code", "name", "active", "plant_code", "production_line_code")
        export_order = ("plant", "production_line", "code", "name", "active")

    def before_import_row(self, row, row_number=None, **kwargs):
        data = {k.lower(): v for k, v in row.items()}
        plant_code = (data.get("plant_code") or data.get("plant") or "").strip()
        pl_code = (data.get("production_line_code") or data.get("production_line") or "").strip()

        if not plant_code:
            raise ValidationError(f"Worker import row {row_number or 'unknown'} missing plant_code")

        try:
            plant = Plant.objects.get(code__iexact=plant_code)
        except Plant.DoesNotExist:
            raise ValidationError(f"Worker import: Plant not found for code '{plant_code}'")

        # attach plant to row so widget mapping works
        row["plant"] = plant.code

        if pl_code:
            pl_qs = ProductionLine.objects.filter(plant=plant, code__iexact=pl_code)
            if not pl_qs.exists():
                # create automatically in clean rebuild scenarios
                ProductionLine.objects.create(plant=plant, code=pl_code, name=pl_code)
            row["production_line"] = pl_code
        else:
            row["production_line"] = ""


class PartyResource(resources.ModelResource):
    class Meta:
        model = Party
        import_id_fields = ("party_code",)
        fields = ("party_code", "name", "contact_person", "contact_number", "email", "tax_id", "is_vendor", "is_customer", "active")
        export_order = ("party_code", "name", "contact_person", "contact_number", "email", "tax_id", "is_vendor", "is_customer", "active")


class UserResource(resources.ModelResource):
    class Meta:
        model = User
        import_id_fields = ("username",)
        fields = ("username", "email", "first_name", "last_name", "is_staff", "is_superuser", "is_active", "password")
        export_order = ("username", "email", "first_name", "last_name", "is_staff", "is_superuser", "is_active")

    def before_save_instance(self, instance, using_transactions, dry_run=False):
        pwd = getattr(instance, "password", None)
        if pwd and not pwd.startswith("pbkdf2_"):
            instance.set_password(pwd)


class UserProfileResource(resources.ModelResource):
    # CSV-friendly columns
    username = fields.Field(column_name="username")
    email = fields.Field(column_name="email")
    first_name = fields.Field(column_name="first_name")
    last_name = fields.Field(column_name="last_name")
    is_staff = fields.Field(column_name="is_staff")
    is_superuser = fields.Field(column_name="is_superuser")
    is_active = fields.Field(column_name="is_active")
    password = fields.Field(column_name="password")  # plaintext; hashed before saving

    plant_code = fields.Field(column_name="plant_code")
    is_plant_admin = fields.Field(column_name="is_plant_admin")

    class Meta:
        model = UserProfile
        import_id_fields = ("username",)
        fields = (
            "username", "email", "first_name", "last_name", "is_staff", "is_superuser", "is_active", "password",
            "plant_code", "is_plant_admin",
        )

    def before_import_row(self, row, **kwargs):
        # normalize whitespace on incoming row values
        for k, v in list(row.items()):
            if isinstance(v, str):
                row[k] = v.strip()

    def before_save_instance(self, instance, using_transactions, dry_run=False):
        """
        Ensure a User exists and is synced from profile fields before saving the UserProfile.
        In dry_run mode we perform validation only (do not create/write User).
        """
        # Determine username from instance or attached user
        username_val = getattr(instance, "username", None)
        if not username_val:
            # If instance.user exists and has username, use it
            user_obj = getattr(instance, "user", None)
            if user_obj:
                username_val = getattr(user_obj, "username", None)

        if not username_val:
            raise ValidationError("CSV must include 'username' column for UserProfile import.")

        # Normalize booleans and simple fields pulled from instance attributes
        # import-export may set these as attributes on the instance
        email_val = getattr(instance, "email", None)
        first_name_val = getattr(instance, "first_name", None)
        last_name_val = getattr(instance, "last_name", None)
        pwd_val = getattr(instance, "password", None)
        is_staff_val = getattr(instance, "is_staff", None)
        is_superuser_val = getattr(instance, "is_superuser", None)
        is_active_val = getattr(instance, "is_active", None)
        plant_code_val = getattr(instance, "plant_code", None)
        ipa_val = getattr(instance, "is_plant_admin", None)

        # Resolve plant if provided (validate)
        if plant_code_val:
            try:
                plant = Plant.objects.get(code__iexact=plant_code_val)
                instance.plant = plant
            except Plant.DoesNotExist:
                raise ValidationError(f"Plant with code '{plant_code_val}' not found.")

        # Interpret IPA boolean
        instance.is_plant_admin = ipa_val in (True, "True", "true", "1", 1, "1")

        # Now handle the User creation/sync
        if dry_run:
            # Dry-run: validate existence/values but do not create DB objects
            user_exists = User.objects.filter(username__iexact=username_val).exists()
            # It's okay if user doesn't exist in dry-run; we'll create on real run.
            # But validate provided booleans or password formats if you want (optional)
            return super().before_save_instance(instance, using_transactions, dry_run=dry_run)

        # Non-dry-run: create or update user and attach before saving profile
        with transaction.atomic():
            user = User.objects.filter(username__iexact=username_val).first()
            created_user = False
            if not user:
                user = User(username=username_val)
                created_user = True

            # Apply fields from profile CSV to user (profile is source-of-truth for creation/import)
            if email_val is not None:
                user.email = email_val
            if first_name_val is not None:
                user.first_name = first_name_val
            if last_name_val is not None:
                user.last_name = last_name_val
            if is_staff_val is not None:
                user.is_staff = str(is_staff_val) in ("True", "true", "1", "1.0", True)
            if is_superuser_val is not None:
                user.is_superuser = str(is_superuser_val) in ("True", "true", "1", "1.0", True)
            if is_active_val is not None:
                user.is_active = str(is_active_val) in ("True", "true", "1", "1.0", True)

            # Password handling: set if provided, else if new user set unusable password
            if pwd_val:
                user.set_password(pwd_val)
            elif created_user and not user.has_usable_password():
                user.set_unusable_password()

            user.save()

            # Attach user to profile instance so profile save has valid FK
            instance.user = user

            # Store transient attrs for downstream signals/helpers if needed
            if email_val is not None:
                setattr(instance, "_email", email_val)
            if first_name_val is not None:
                setattr(instance, "_first_name", first_name_val)
            if last_name_val is not None:
                setattr(instance, "_last_name", last_name_val)
            if is_staff_val is not None:
                setattr(instance, "_is_staff", str(is_staff_val) in ("True", "true", "1", "1.0", True))
            if is_superuser_val is not None:
                setattr(instance, "_is_superuser", str(is_superuser_val) in ("True", "true", "1", "1.0", True))
            if is_active_val is not None:
                setattr(instance, "_is_active", str(is_active_val) in ("True", "true", "1", "1.0", True))
            if pwd_val:
                setattr(instance, "_password_plain", pwd_val)

            # mark origin/timestamp so signals know this was an import-driven profile change
            setattr(instance, "_update_origin", "import")
            setattr(instance, "_updated_at", timezone.now())

        return super().before_save_instance(instance, using_transactions, dry_run=dry_run)