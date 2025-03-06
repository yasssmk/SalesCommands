from django.urls import path
from .views import AccountAPIView, AccountChoicesView


urlpatterns = [

    path('', AccountAPIView.as_view(), name='account-list'),  # For GET and POST requests
    path('<int:pk>/', AccountAPIView.as_view(), name='account-detail'),  # For PUT and DELETE by ID 
    path('account-types/', AccountChoicesView.as_view(), name='account-types'),  # For GET request to retrieve account types
    

    path('<int:pk>/signals/', AccountAPIView.as_view(), name='account-signals'),
    path('<int:pk>/field-signals/', AccountAPIView.as_view(), name='account-field-signals'),
    path('<int:pk>/hierarchy/', AccountAPIView.as_view(), name='account-hierarchy'),
]