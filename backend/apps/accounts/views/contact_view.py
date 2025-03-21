from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from core.apps_shared_methods import BaseAPIView
from apps.core_apps.views import SignalAwareViewMixin
from ..models import Contact
from ..serializers import ContactSerializer
from django.utils.translation import gettext_lazy as _
from core.error_messages import CoreErrorMessages, AccountErrorMessages
from core.exceptions import StandardizedValidationError

class ContactAPIView(BaseAPIView, SignalAwareViewMixin):
    """
    API View for Contact management with signal awareness.
    """
    
    queryset = Contact.objects.select_related(
        'account'
    )
    
    serializer_class = ContactSerializer
    entity_name = 'contact'

    mass_update_allowed_fields = {'job_title', 'influence_level'}

    def get_queryset(self):
        """Extend base queryset with contact-specific filtering"""
        try:
            queryset = super().get_queryset()
            
            filter_mappings = {
                'account_id': 'account_id',
                'influence_level': 'influence_level',
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
                        Q(job_title__icontains=search_term)
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
            old_org_unit = instance.organization_unit_id
            
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
                    
                    return serializer
                    
            raise StandardizedValidationError(serializer.errors)
        except Exception as exc:
            return self.handle_exception(exc)

class ContactChoicesView(APIView):
    """
    API endpoint for retrieving contact-related choices.
    """
    def get(self, request):
        """Get common choices for contacts"""
        # Example influence levels - adjust as needed
        influence_levels = [
            {'value': 'DECISION_MAKER', 'label': _('Decision Maker')},
            {'value': 'INFLUENCER', 'label': _('Influencer')},
            {'value': 'APPROVER', 'label': _('Approver')},
            {'value': 'USER', 'label': _('User')},
            {'value': 'CHAMPION', 'label': _('Champion')},
            {'value': 'BLOCKER', 'label': _('Blocker')},
        ]
        
        return Response({
            'influence_levels': influence_levels
        })
