from django.urls import path
from .views import AccountOrganizationUnitAPIView


urlpatterns = [
    path('', AccountOrganizationUnitAPIView.as_view(), name='organization-list'),  # For GET and POST requests
    path('<int:pk>/', AccountOrganizationUnitAPIView.as_view(), name='organization-detail'),  # For PUT and DELETE by ID 
]