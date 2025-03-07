from django.urls import path
from .views import AccountOrganizationUnitAPIView, OrganizationUnitChoicesView
from apps.core_apps.views import StandardDepartmentChoicesView


urlpatterns = [
    path('', AccountOrganizationUnitAPIView.as_view(), name='organization-list'),  # For GET and POST requests
    path('<int:pk>/', AccountOrganizationUnitAPIView.as_view(), name='organization-detail'),  # For PUT and DELETE by ID

    # Signal-related endpoints
    path('<int:pk>/signals/', AccountOrganizationUnitAPIView.as_view(), name='organization-signals'),
    path('<int:pk>/field-signals/', AccountOrganizationUnitAPIView.as_view(), name='organization-field-signals'),
    path('<int:pk>/hierarchy/', AccountOrganizationUnitAPIView.as_view(), name='organization-hierarchy'),
    
    # Choice endpoints
    path('unit-types/', OrganizationUnitChoicesView.as_view(), name='organization-unit-types'),
    path('standard-departments/', StandardDepartmentChoicesView.as_view(), name='standard-departments'),
] 