# apps/accounts/views/techstack_view.py
from django.db.models import Q
from rest_framework.decorators import action
from rest_framework.response import Response
from core.apps_shared_methods import BaseAPIView
from apps.core_apps.models import StandardDepartment
from ..models import TechStack
from ..serializers import TechStackSerializer
from django.utils.translation import gettext_lazy as _


class TechStackAPIView(BaseAPIView):
    """
    API View for TechStack management with signal-based evaluation data.
    """
    
    queryset = TechStack.objects.select_related('account')
    serializer_class = TechStackSerializer
    entity_name = 'techstack'

    mass_update_allowed_fields = {'tech_name', 'notes'}

    def get_queryset(self):
        """Extend base queryset with tech stack-specific filtering"""
        queryset = super().get_queryset()
            
        filter_mappings = {
            'account_id': 'account_id',
            'tech_name': 'tech_name__icontains',
            'category': 'category',
            'search': None  # Special handling for search
        }
            
        for param, field in filter_mappings.items():
            values = self.request.query_params.get(param)
            if values and field:
                queryset = queryset.filter(**{field: values.strip()})
            elif param == 'search' and values:
                search_term = values.strip()
                queryset = queryset.filter(
                    Q(tech_name__icontains=search_term) | 
                    Q(notes__icontains=search_term) |
                    Q(category__icontains=search_term)
                )
                    
        return queryset
    
    def get_serializer_context(self):
        """Add filter parameters to serializer context"""
        context = super().get_serializer_context()
        
        # Get department filter if specified
        department_id = self.request.query_params.get('department_id')
        if department_id:
            try:
                department = StandardDepartment.objects.get(id=department_id)
                context['department'] = department
            except StandardDepartment.DoesNotExist:
                # Just ignore invalid department
                pass
        
        # Get source contact filter if specified
        source_contact_id = self.request.query_params.get('source_contact_id')
        if source_contact_id:
            from ..models import Contact
            try:
                contact = Contact.objects.get(id=source_contact_id)
                context['source_contact'] = contact
            except Contact.DoesNotExist:
                # Just ignore invalid contact
                pass
        
        # Get min confirmations filter if specified
        min_confirmations = self.request.query_params.get('min_confirmations')
        if min_confirmations and min_confirmations.isdigit():
            context['min_confirmations'] = int(min_confirmations)
            
        # Set 'many' flag for serializer context
        context['many'] = self.action == 'list'
        
        return context
    
    @action(detail=True, methods=['get'])
    def evaluation(self, request, pk=None):
        """
        Get tech stack evaluation data with filtering options.
        
        GET /api/techstacks/{id}/evaluation/
        """
        try:
            tech_stack = self.get_object()
            
            # Parse filter parameters
            department_id = request.query_params.get('department_id')
            field_name = request.query_params.get('field_name')
            min_confirmations = request.query_params.get('min_confirmations')
            source_contact_id = request.query_params.get('source_contact_id')
            
            # Build filters
            filters = {}
            
            if department_id:
                try:
                    department = StandardDepartment.objects.get(id=department_id)
                    filters['department'] = department
                except StandardDepartment.DoesNotExist:
                    pass
            
            if field_name:
                # Convert from comma-separated string to list if needed
                if ',' in field_name:
                    field_names = [name.strip() for name in field_name.split(',')]
                    filters['field_names'] = field_names
                else:
                    filters['field_names'] = [field_name]
            
            if min_confirmations and min_confirmations.isdigit():
                filters['min_confirmations'] = int(min_confirmations)
            
            if source_contact_id:
                from ..models import Contact
                try:
                    contact = Contact.objects.get(id=source_contact_id)
                    filters['source_contact'] = contact
                except Contact.DoesNotExist:
                    pass

            
            # Get tech stack evaluation data with filters
            evaluation_data = tech_stack.get_evaluation_data(**filters)
            
            return Response(evaluation_data)
            
        except Exception as e:
            return self.handle_exception(e)
    
    def dispatch(self, request, *args, **kwargs):
        """Custom dispatch to handle different endpoints"""
        # Check if this is an evaluation endpoint
        path = request.path.split('/')
        
        if len(path) > 4:
            endpoint_type = path[4]  # Get the endpoint type
            
            if endpoint_type == 'evaluation':
                if request.method == 'GET':
                    return self.get_evaluation(request, *args, **kwargs)
        
        # Default to standard dispatch
        return super().dispatch(request, *args, **kwargs)
    

                
