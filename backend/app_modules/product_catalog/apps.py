# app_modules/product_catalog/apps.py

from django.apps import AppConfig


class ProductCatalogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_modules.product_catalog'
    label = 'product_catalog'
    verbose_name = 'Product Catalog'
