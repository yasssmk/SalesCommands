# app_modules/quotas/apps.py
from django.apps import AppConfig


class QuotasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_modules.quotas'
    label = 'quotas'
    verbose_name = 'Quotas (personal Sales objectives)'
