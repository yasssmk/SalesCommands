# backend/app_modules/territories/apps.py
from django.apps import AppConfig


class TerritoriesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_modules.territories'
    label = 'module_territories'
    verbose_name = 'Territories Module'