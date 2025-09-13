from django.apps import AppConfig

class GarmentAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'garment_app'         # the actual Python package name
    verbose_name = 'Masters'    # 👈 this text will appear in the admin sidebar
