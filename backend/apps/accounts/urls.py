from django.urls import path
from .views import AccountAPIView, AccountHierarchyAPIView


urlpatterns = [
    path('', AccountAPIView.as_view(), name='account-list'),  # For GET and POST requests
    path('<int:pk>/', AccountAPIView.as_view(), name='account-detail'),  # For PUT and DELETE by ID 
]