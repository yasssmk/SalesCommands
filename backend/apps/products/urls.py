from django.urls import path
from .views import (
    ProductAPIView,
    PricingAPIView,
    BillingCycleAPIView
)

app_name = 'products'

urlpatterns = [
    # Product URLs
    path('', ProductAPIView.as_view(), name='product-list'),  # GET, POST
    path('<int:pk>/', ProductAPIView.as_view(), name='product-detail'),  # GET, PUT, PATCH, DELETE
    
    # Pricing URLs
    path('pricing/', PricingAPIView.as_view(), name='pricing-list'),  # GET, POST
    path('pricing/<int:pk>/', PricingAPIView.as_view(), name='pricing-detail'),  # GET, PUT, PATCH, DELETE
    
    # Billing Cycle URLs
    path('billing-cycles/', BillingCycleAPIView.as_view(), name='billing-cycle-list'),  # GET, POST
    path('billing-cycles/<int:pk>/', BillingCycleAPIView.as_view(), name='billing-cycle-detail'),  # GET, PUT, PATCH, DELETE
]