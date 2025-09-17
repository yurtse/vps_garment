# apps/masters/auth_config.py
from django.contrib.auth.apps import AuthConfig


class CustomAuthConfig(AuthConfig):
    # Override the displayed name in the admin sidebar
    verbose_name = "Users/Permissions"
