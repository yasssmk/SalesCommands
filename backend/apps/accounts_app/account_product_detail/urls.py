from django.urls import path
from .views import AccountProductDetailView

urlpatterns = [
    # List and Create
    path(
        'accounts/<uuid:account_id>/product-details/', 
        AccountProductDetailView.as_view(),
        name='account-product-detail-list'
    ),
    
    # Retrieve, Update, Delete
    path(
        'accounts/<uuid:account_id>/product-details/<uuid:pk>/', 
        AccountProductDetailView.as_view(),
        name='account-product-detail-detail'
    ),
    
    # Bulk operations with IDs in query params
    path(
        'accounts/<uuid:account_id>/product-details/bulk/', 
        AccountProductDetailView.as_view(),
        name='account-product-detail-bulk'
    ),
    
    # Summary view
    path(
        'accounts/<uuid:account_id>/product-details/summary/', 
        AccountProductDetailView.as_view({'get': 'summary'}),
        name='account-product-detail-summary'
    ),
    
    # Whitespace analysis
    path(
        'accounts/<uuid:account_id>/product-details/whitespace/', 
        AccountProductDetailView.as_view({'get': 'whitespace'}),
        name='account-product-detail-whitespace'
    ),
]