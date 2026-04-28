# app_modules/tech_catalog/constants.py
"""
Constants for the TechCatalog module.

The TechCatalog is a tenant-level master list of technologies (Salesforce,
HubSpot, Slack, Notion, etc.) curated by tenant admins and consumed
read-only by sales-side modules (Product associations, TechStackSignal,
pre-call game plans).

The module is intentionally minimal — no workflow status, no aliases, no
category taxonomy, no derived properties. Anything beyond simple CRUD on
a small reference list is out of scope and lives elsewhere if needed.

This file therefore exposes a single symbol:

    TECH_CATALOG_CACHE_TAG — the cache tag used by the ViewSet to bust
    all per-tenant caches that depend on TechCatalog data after any
    write (create / update / delete). The tag is paired with the
    requesting user's client_id when calling
    `core.cache_utils.invalidate_tag(client_id, TECH_CATALOG_CACHE_TAG)`,
    ensuring that cache invalidation never crosses tenants.
"""

# Cache tag — see module docstring above for usage contract.
TECH_CATALOG_CACHE_TAG = 'tech_catalog'