# app_modules/tech_catalog/apps.py
"""
Django AppConfig for the (removed) TechCatalog module.

MIGRATIONS-ONLY APP — no models, no views, no URLs, no permissions.

The TechCatalog was a tenant-level master list of technologies that
TechStackSignal and PainSignal pointed at by FK. S10 replaced it with
free-text identity on the signal itself (`tech_name` plus the derived
`tech_name_normalized`), so the model, its CRUD API, its permissions
registry entry and its feature flag are all gone — see migration
0002_delete_techcatalog.

Why this app is still in INSTALLED_APPS
--------------------------------------
Five historical migrations in `module_signals` declare
`('tech_catalog', '0001_initial')` in their dependencies:

    0008_techstack_canonical_refactor
    0009_painsignal_related_techstack_and_more
    0013_alter_techstacksignal_tech_catalog_entry
    0014_drop_painimpact_add_impactsignal_and_scope
    0023_techstacksignal_is_competitor_and_more

Removing the app from INSTALLED_APPS would make those dependencies
unresolvable and break `migrate` from zero — including every test-database
build. The app therefore stays registered purely to keep its migration
history in the graph.

It can be dropped entirely once the signals migrations are squashed past
0023. Until then this package contains nothing but `migrations/`.
"""

from django.apps import AppConfig


class TechCatalogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_modules.tech_catalog'
    label = 'tech_catalog'
    verbose_name = 'Tech Catalog (removed — migrations only)'
