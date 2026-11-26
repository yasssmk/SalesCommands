# app_modules/product_catalog/urls.py

from django.urls import path


app_name = 'product_catalog'


def get_urlpatterns():
    from app_modules.product_catalog.views import ProductCatalogViewSet, SellerProfileViewSet

    return [
        # The tenant's seller profile (sprint 2 Game Plan, G6): GET / PUT only.
        path(
            'seller-profile/',
            SellerProfileViewSet.as_view({
                'get': 'retrieve',
                'put': 'update',
            }),
            name='seller-profile',
        ),
        path(
            '',
            ProductCatalogViewSet.as_view({
                'get': 'list',
                'post': 'create',
            }),
            name='list',
        ),
        path(
            '<uuid:pk>/',
            ProductCatalogViewSet.as_view({
                'get': 'retrieve',
                'put': 'update',
                'patch': 'partial_update',
                'delete': 'destroy',
            }),
            name='detail',
        ),
    ]


urlpatterns = get_urlpatterns()
