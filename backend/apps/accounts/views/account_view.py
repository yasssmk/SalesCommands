# apps/accounts/views.py
from rest_framework.views import APIView
from django.db import transaction
from rest_framework.response import Response
from core.exceptions import StandardizedValidationError
from core.apps_shared_methods import BaseAPIView
from ..models import Account
from ..serializers import AccountSerializer
from django.utils.translation import gettext_lazy as _
from core.error_messages import CoreErrorMessages, AccountErrorMessages
from datetime import datetime
from apps.core_apps.views import SignalAwareViewMixin, HistoricalTrackingViewMixin

class AccountAPIView(BaseAPIView, SignalAwareViewMixin, HistoricalTrackingViewMixin):
    """
    API View for Account management with parent-child relationship handling.
    """
    
    queryset = Account.objects.select_related(
        'parent_company', 
        'account_owner', 
        'team_owner'
    ).prefetch_related('direct_child_companies')
    
    serializer_class = AccountSerializer
    entity_name = 'account'

    mass_update_allowed_fields = {'type', 'classification', 'account_owner_id', 'team_owner_id'}

    def get_queryset(self):
        """Extend base queryset with account-specific filtering"""
        queryset = super().get_queryset()
        
        filter_mappings = {
            'parent_ids': 'parent_company_id__in',
            'types': 'type__in',
            'classifications': 'classification__in'
        }
        
        try:
            for param, field in filter_mappings.items():
                values = self.request.query_params.get(param)
                if values:
                    filter_list = [v.strip() for v in values.split(',')]
                    queryset = queryset.filter(**{field: filter_list})
                    
        except ValueError:
            raise StandardizedValidationError(CoreErrorMessages.INVALID_FILTER)
            
        return queryset

    def get_serializer_context(self):
        """Add signal info flag to serializer context"""
        context = super().get_serializer_context()
        
        # Check if signal info was requested via query param
        include_signal_info = self.request.query_params.get('include_signal_info', 'false').lower() == 'true'
        context['include_signal_info'] = include_signal_info
        
        return context

    def _validate_parent_company(self, parent_id, client_id):
        """Validate parent company exists and belongs to same client"""
        if parent_id:
            try:
                parent = Account.objects.get(id=parent_id)
                if str(parent.client_id) != str(client_id):
                    raise StandardizedValidationError(AccountErrorMessages.INVALID_PARENT)
                return parent
            except Account.DoesNotExist:
                raise StandardizedValidationError(AccountErrorMessages.PARENT_NOT_FOUND)
        return None

    def _update_instance(self, instance, data, partial, client_id):
            """Optimized update with minimal queries"""
            self.validate_client_id(instance)
            
            # Track fields that need refresh
            refresh_fields = set()
            
            # Store old values for relationship changes
            old_parent = instance.parent_company_id
            old_team = instance.team_owner_id
            
            try:
                serializer = self.serializer_class(
                    instance,
                    data=data,
                    partial=partial,
                    context={'request': self.request, 'client_id': client_id}
                )
                
                if serializer.is_valid():
                    with transaction.atomic():
                        updated = serializer.save()
                        
                        # Only refresh changed relationships
                        if old_parent != updated.parent_company_id:
                            refresh_fields.add('parent_company')
                            if old_parent:
                                Account.objects.filter(id=old_parent).update(
                                    updated_at=datetime.now()
                                )
                        
                        if old_team != updated.team_owner_id:
                            refresh_fields.add('team_owner')
                        
                        if refresh_fields:
                            updated.refresh_from_db(fields=refresh_fields)
                        
                        return serializer
                
                # Extract and format error message
                raise StandardizedValidationError(serializer.errors)
                    
            except Exception as e:
                raise StandardizedValidationError(str(e))

    def dispatch(self, request, *args, **kwargs):
        """Custom dispatch to handle different endpoints"""
        # Check if this is a signals or field-signals endpoint
        path = request.path.split('/')
        
        # Path will contain segments like ['', 'api', 'accounts', '1', 'signals', '']
        if len(path) > 4:
            endpoint_type = path[4]  # Get the endpoint type
            
            if endpoint_type == 'signals':
                if request.method == 'GET':
                    return self.get_signals(request, *args, **kwargs)
            
            elif endpoint_type == 'field-signals':
                if request.method == 'GET':
                    return self.get_field_signals(request, *args, **kwargs)
            
            elif endpoint_type == 'hierarchy':
                if request.method == 'GET':
                    return self.get_hierarchy(request, *args, **kwargs)
        
        # Default to standard dispatch
        return super().dispatch(request, *args, **kwargs)
    
        

class AccountChoicesView(APIView):
    """
    API endpoint for retrieving account type and classification choices.
    No client scoping needed as these are global choices.
    """
    def get(self, request):
        return Response({
            'types': Account.get_account_types(),
            'classifications': Account.get_account_classifications()
        })