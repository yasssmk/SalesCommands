from django.urls import path
from .views import (
    ProductAPIView,
    PricingAPIView,
)

app_name = 'products'

urlpatterns = [
    # Product URLs
    path('', ProductAPIView.as_view(), name='product-list'),  # GET, POST
    path('<int:pk>/', ProductAPIView.as_view(), name='product-detail'),  # GET, PUT, PATCH, DELETE
    
    # Pricing URLs
    path('pricing/', PricingAPIView.as_view(), name='pricing-list'),  # GET, POST
    path('pricing/<int:pk>/', PricingAPIView.as_view(), name='pricing-detail'),  # GET, PUT, PATCH, DELETE
    
]