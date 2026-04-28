# app_modules/tech_catalog/apps.py
"""
Django AppConfig for the TechCatalog module.

The TechCatalog is a tenant-level master catalog of technologies
(Salesforce, HubSpot, etc.) used by the sales organization. It is
administered exclusively by tenant admins; reads are open tenant-wide
so that sales reps can consume entries via AsyncTechCatalogSelect.

App label `tech_catalog` is used:
  * As the registry key in permissions/registry/tech_catalog_registry.py
  * As the OWNERSHIP_MAP key in permissions/ownership.py
  * As the `module` attribute on TechCatalogViewSet
"""

from django.apps import AppConfig


class TechCatalogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_modules.tech_catalog'
    label = 'tech_catalog'
    verbose_name = 'Tech Catalog'