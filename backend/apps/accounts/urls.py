from django.urls import path
from .views import AccountAPIView, get_account_choices


urlpatterns = [
    path('', AccountAPIView.as_view(), name='account-list'),  # For GET and POST requests
    path('<uuid:pk>/', AccountAPIView.as_view(), name='account-detail'),  # For PUT and DELETE by ID 
    path('account-types/', get_account_choices, name='account-types'),  # For GET request to retrieve account types
]