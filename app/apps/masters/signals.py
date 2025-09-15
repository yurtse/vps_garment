# garment_app/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction

from .models import UserProfile

User = get_user_model()

# Helper to update/create User from profile
def _apply_profile_to_user(profile):
    """
    Apply relevant fields from profile to linked User.
    Uses optimistic timestamp check against profile.last_synced_to_user to avoid needless writes.
    """
    # gather profile timestamps
    profile_ts = getattr(profile, "_updated_at", None) or profile.updated_at
    if profile.last_synced_to_user and profile_ts and profile_ts <= profile.last_synced_to_user:
        # profile changes already synced or older than last sync -> skip
        return

    # ensure user exists
    user = profile.user
    # Update user fields from profile if they differ. We only update a minimal set (username/email, is_staff/is_superuser,is_active,name)
    changed = False
    # You may want to map additional fields from profile (not present now)
    # For safety, we'll only update username/email/is_active/is_staff/is_superuser if attributes exist on profile (via transient attrs)
    uattrs = {}
    if hasattr(profile, "_username"):
        uattrs["username"] = profile._username
    if hasattr(profile, "_email"):
        uattrs["email"] = profile._email
    if hasattr(profile, "_first_name"):
        uattrs["first_name"] = profile._first_name
    if hasattr(profile, "_last_name"):
        uattrs["last_name"] = profile._last_name
    if hasattr(profile, "_is_staff"):
        uattrs["is_staff"] = profile._is_staff
    if hasattr(profile, "_is_superuser"):
        uattrs["is_superuser"] = profile._is_superuser
    if hasattr(profile, "_is_active"):
        uattrs["is_active"] = profile._is_active
    if hasattr(profile, "_password_plain") and profile._password_plain:
        # set password
        user.set_password(profile._password_plain)
        changed = True

    # apply collected attrs
    for k, v in uattrs.items():
        if getattr(user, k, None) != v:
            setattr(user, k, v)
            changed = True

    if changed:
        # mark that this save originates from sync to avoid reverse sync
        setattr(user, "_update_origin", "sync_from_profile")
        setattr(user, "_updated_at", timezone.now())
        user.save()
    # update profile.last_synced_to_user
    profile.last_synced_to_user = timezone.now()
    profile.save(update_fields=["last_synced_to_user"])


# Helper to apply user -> profile updates
def _apply_user_to_profile(user):
    """
    Pull relevant fields from User into profile. Uses optimistic timestamp check
    based on user._updated_at (set by admin save) vs profile.last_synced_from_user.
    """
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        # create a new profile if missing
        profile = UserProfile.objects.create(user=user)

    user_ts = getattr(user, "_updated_at", None)
    if user_ts is None:
        # no explicit update timestamp; proceed but guard with last_synced_from_user
        user_ts = timezone.now()

    if profile.last_synced_from_user and user_ts <= profile.last_synced_from_user:
        return

    # Avoid loops: when we save profile as part of sync, mark origin
    # Apply fields (we only map a minimal safe set)
    changed = False
    if getattr(profile, "plant", None) is None and hasattr(user, "_plant_code"):
        # optional: resolve plant by code if provided on user transient attr
        pass

    # map name/email flags if present on user as transient attributes
    if hasattr(user, "_email"):
        if profile.user.email != user._email:
            profile.user.email = user._email
            profile.user.save(update_fields=["email"])
    # Map other flags if provided
    if hasattr(user, "_is_plant_admin"):
        if profile.is_plant_admin != user._is_plant_admin:
            profile.is_plant_admin = user._is_plant_admin
            changed = True

    if changed:
        # prevent reverse-loop by setting marker
        setattr(profile, "_update_origin", "sync_from_user")
        profile.save()
    profile.last_synced_from_user = timezone.now()
    profile.save(update_fields=["last_synced_from_user"])


@receiver(post_save, sender=UserProfile)
def userprofile_post_save(sender, instance: UserProfile, created, **kwargs):
    """
    Sync forward to User when UserProfile is changed via profile UI or CSV import.
    Only run when origin indicates profile-driven change.
    """
    origin = getattr(instance, "_update_origin", None)
    if origin in ("profile_ui", "import", "profile_admin"):
        # optimistic check already handled in helper
        try:
            with transaction.atomic():
                _apply_profile_to_user(instance)
        except Exception:
            # avoid propagating exceptions from sync; admin / resource should report them separately
            pass


@receiver(post_save, sender=User)
def user_post_save(sender, instance: User, created, **kwargs):
    """
    Sync to UserProfile when the User was edited via User admin (origin 'user_ui').
    """
    origin = getattr(instance, "_update_origin", None)
    if origin in ("user_ui",):
        try:
            with transaction.atomic():
                _apply_user_to_profile(instance)
        except Exception:
            pass
