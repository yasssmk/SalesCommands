
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.core_apps.models import StandardDepartment

class StandardDepartmentChoicesView(APIView):
    """
    API endpoint for retrieving standard department choices.
    """
    def get(self, request):
        """Get list of all standard departments in a formatted structure"""
        return Response({
            'standard_departments': [
                {
                    'value': dept.id, 
                    'label': dept.name,
                    'department_type': dept.department_type if hasattr(dept, 'department_type') else None
                } 
                for dept in StandardDepartment.objects.all().order_by('name')
            ]
        })