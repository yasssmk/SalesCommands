from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from core.apps_shared_methods import BaseAPIView
from apps.core_apps.models import StandardDepartment
from ..models import Contact
from ..serializers import ContactSerializer
from django.utils.translation import gettext_lazy as _
from core.error_messages import CoreErrorMessages, AccountErrorMessages
from core.exceptions import StandardizedValidationError
from ..services.contact_service import ContactService

class ContactAPIView(BaseAPIView):
    """
    API View for Contact management with signal awareness.
    """
    
    queryset = Contact.objects.select_related(
        'account', 'standard_department'
    )
    
    serializer_class = ContactSerializer
    entity_name = 'contact'

    mass_update_allowed_fields = {'job_title', 'influence_level', 'department', 'standard_department_id'}

    def dispatch(self, request, *args, **kwargs):
        """
        Route requests to appropriate handler methods based on URL path
        """
        # Extract the last part of the URL path to determine the action
        path = request.path_info.strip('/').split('/')
        action = path[-1] if path else None
        
        # Map actions to methods
        if action == 'toggle-email-validity':
            return self.toggle_email_validity(request, *args, **kwargs)
        elif action == 'toggle-phone-validity':
            return self.toggle_phone_validity(request, *args, **kwargs)
            
        # Otherwise fall back to standard REST methods
        return super().dispatch(request, *args, **kwargs)


    def get_queryset(self):
        """Extend base queryset with contact-specific filtering"""
        try:
            queryset = super().get_queryset()
            
            filter_mappings = {
                'account_id': 'account_id',
                'influence_level': 'influence_level',
                'department': 'department__icontains',
                'standard_department_id': 'standard_department_id',
                'search': None  # Special handling for search
            }
            
            for param, field in filter_mappings.items():
                values = self.request.query_params.get(param)
                if values and field:
                    queryset = queryset.filter(**{field: values.strip()})
                elif param == 'search' and values:
                    search_term = values.strip()
                    queryset = queryset.filter(
                        Q(first_name__icontains=search_term) | 
                        Q(last_name__icontains=search_term) |
                        Q(email__icontains=search_term) |
                        Q(job_title__icontains=search_term) |
                        Q(department__icontains=search_term)
                    )
                        
            return queryset
                
        except ValueError as exc:
            raise StandardizedValidationError(CoreErrorMessages.INVALID_FILTER)

    
    def _update_instance(self, instance, data, partial, client_id):
        """Optimized update with minimal queries"""
        try:
            self.validate_client_id(instance)
            
            # Store old values for relationship changes
            old_account = instance.account_id
            
            # Store original values for tracking changes
            original_values = {}
            for field_name in data.keys():
                if hasattr(instance, field_name):
                    original_values[field_name] = getattr(instance, field_name)
            
            serializer = self.serializer_class(
                instance,
                data=data,
                partial=partial,
                context={'request': self.request, 'client_id': client_id}
            )
            
            if serializer.is_valid():
                with transaction.atomic():
                    # Prevent changing account
                    if 'account_id' in data and str(data['account_id']) != str(old_account):
                        raise StandardizedValidationError(AccountErrorMessages.CHANGE_CONTACT_ACCOUNT)
                    
                    updated = serializer.save()
                    
                    # Manual historical tracking if needed
                    user = self.request.user if hasattr(self.request, 'user') else None
                    for field_name, old_value in original_values.items():
                        new_value = getattr(updated, field_name)
                        if old_value != new_value and hasattr(updated, 'track_field_change'):
                            updated.track_field_change(field_name, old_value, new_value, user)
                    
                    return serializer
                    
            raise StandardizedValidationError(serializer.errors)
        except Exception as exc:
            return self.handle_exception(exc)
        
    def toggle_email_validity(self, request, pk=None, *args, **kwargs):
        """Toggle the email_is_valid field for a contact"""
        try:
            contact = self.get_object()
            self.validate_client_id(contact)
            
            user = request.user if hasattr(request, 'user') else None
            result = ContactService.toggle_email_validity(contact, user)
            
            return Response(result)
        except Exception as exc:
            return self.handle_exception(exc)
            
    def toggle_phone_validity(self, request, pk=None, *args, **kwargs):
        """Toggle the phone_is_valid field for a contact"""
        try:
            contact = self.get_object()
            self.validate_client_id(contact)
            
            user = request.user if hasattr(request, 'user') else None
            result = ContactService.toggle_phone_validity(contact, user)
            
            return Response(result)
        except Exception as exc:
            return self.handle_exception(exc)

class ContactChoicesView(APIView):
    """
    API endpoint for retrieving contact-related choices.
    """
    def get(self, request):
        """Get common choices for contacts"""
        from ..models import InfluenceLevel
        
        # Get influence levels from the model
        influence_levels = [
            {'value': choice[0], 'label': choice[1]} 
            for choice in InfluenceLevel.choices
        ]
        
        # Get standard departments
        standard_departments = [
            {'id': dept.id, 'name': dept.name, 'display_name': dept.get_name_display()}
            for dept in StandardDepartment.objects.all()
        ]
        
        return Response({
            'influence_levels': influence_levels,
            'standard_departments': standard_departments
        })