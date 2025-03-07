# apps/accounts_app/contacts/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from core.apps_shared_methods import BaseAPIView
from apps.core_apps.views import SignalAwareViewMixin
from .models import Contact
from .serializers import ContactSerializer
from django.utils.translation import gettext_lazy as _
from core.error_messages import CoreErrorMessages, AccountErrorMessages
from core.exceptions import StandardizedValidationError
from apps.accounts_app.org_units.models import AccountOrganizationUnit

class ContactAPIView(BaseAPIView, SignalAwareViewMixin):
    """
    API View for Contact management with signal awareness.
    """
    
    queryset = Contact.objects.select_related(
        'account',
        'organization_unit',
    )
    
    serializer_class = ContactSerializer
    entity_name = 'contact'

    mass_update_allowed_fields = {'job_title', 'influence_level', 'organization_unit_id'}

    def get_queryset(self):
        """Extend base queryset with contact-specific filtering"""
        try:
            queryset = super().get_queryset()
            
            filter_mappings = {
                'account_id': 'account_id',
                'organization_unit_id': 'organization_unit_id',
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

    def _validate_organization_unit(self, org_unit_id, account_id, client_id):
        """Validate org unit exists and belongs to the same account and client"""
        if org_unit_id:
            try:
                org_unit = AccountOrganizationUnit.objects.get(id=org_unit_id)
                if str(org_unit.client_id) != str(client_id):
                    raise StandardizedValidationError(AccountErrorMessages.INVALID_ORG_UNIT)
                    
                if str(org_unit.account_id) != str(account_id):
                    raise StandardizedValidationError(AccountErrorMessages.ORG_UNIT_ACCOUNT_MISMATCH)
                    
                return org_unit
            
            except AccountOrganizationUnit.DoesNotExist:
                raise StandardizedValidationError(AccountErrorMessages.ORG_UNIT_NOT_FOUND)
            
        return None

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
                    
                    # Validate organization unit if changing
                    if 'organization_unit_id' in data and data['organization_unit_id'] != old_org_unit:
                        self._validate_organization_unit(
                            data['organization_unit_id'], 
                            instance.account_id, 
                            client_id
                        )
                    
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
