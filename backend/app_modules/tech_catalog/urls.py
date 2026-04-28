# app_modules/tech_catalog/urls.py
"""
URL configuration for the TechCatalog module.

Lazy `get_urlpatterns()` mirrors the pattern used by
app_modules/accounts/urls.py — the imports happen at call time so the
module can be loaded by Django's URL resolver without triggering the
view layer's own imports at app-loading time. This avoids circular
import surprises when the views module reaches into core /
permissions / cache utilities.

Mount point (defined in salescommands/urls.py):
    /tech-catalog/  →  app_modules/tech_catalog/urls.py

All paths below are relative to that mount point. The resulting
absolute routes are:

    GET    /tech-catalog/             →  list
    POST   /tech-catalog/             →  create
    GET    /tech-catalog/<uuid>/      →  retrieve
    PUT    /tech-catalog/<uuid>/      →  update          (treated as PATCH on the ViewSet)
    PATCH  /tech-catalog/<uuid>/      →  partial_update
    DELETE /tech-catalog/<uuid>/      →  destroy

No bulk endpoints, no choices endpoint, no custom @action methods —
the catalog is intentionally a flat REST surface.
"""

from django.urls import path


app_name = 'tech_catalog'


def get_urlpatterns():
    """Lazy import to avoid circular imports at Django startup."""
    from app_modules.tech_catalog.views import TechCatalogViewSet

    return [
        # =====================================================================
        # CRUD — list + create
        # =====================================================================
        path(
            '',
            TechCatalogViewSet.as_view({
                'get': 'list',
                'post': 'create',
            }),
            name='list',
        ),

        # =====================================================================
        # CRUD — retrieve / update / partial_update / destroy
        # =====================================================================
        path(
            '<uuid:pk>/',
            TechCatalogViewSet.as_view({
                'get': 'retrieve',
                'put': 'update',
                'patch': 'partial_update',
                'delete': 'destroy',
            }),
            name='detail',
        ),
    ]


urlpatterns = get_urlpatterns()