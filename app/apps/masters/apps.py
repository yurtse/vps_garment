from django.apps import AppConfig

class MastersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.masters'         # the actual Python package name
    verbose_name = 'Masters'    # 👈 this text will appear in the admin sidebar
