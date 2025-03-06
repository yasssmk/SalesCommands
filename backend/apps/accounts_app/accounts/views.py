# apps/accounts/views.py
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import serializers
from django.db import transaction
from core.exceptions import StandardizedValidationError
from core.apps_shared_methods import BaseAPIView
from .models import Account
from .serializers import AccountSerializer
from django.utils.translation import gettext_lazy as _
from core.error_messages import CoreErrorMessages, AccountErrorMessages
from datetime import datetime

class AccountAPIView(BaseAPIView):
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
    
    def get_signals(self, request, pk=None, *args, **kwargs):
        """Get all signals related to this account"""
        try:
            account = self.get_objects([pk]).first()
            if not account:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Get query params for filtering
            field_name = request.query_params.get('field_name')
            category = request.query_params.get('category')
            include_expired = request.query_params.get('include_expired', 'false').lower() == 'true'
            
            # Get related signals
            signals = account.get_related_signals(
                field_name=field_name,
                category=category,
                include_expired=include_expired
            )
            
            # Prepare response with categorized signals
            result = {}
            for status, queryset in signals.items():
                if queryset.exists():
                    from apps.sales_insight.serializers import SignalSerializer
                    result[status] = SignalSerializer(queryset, many=True).data
                else:
                    result[status] = []
            
            return Response(result)
            
        except Exception as exc:
            return self.handle_exception(exc)
    
    def get_field_signals(self, request, pk=None, *args, **kwargs):
        """Get signals related to a specific field"""
        try:
            account = self.get_objects([pk]).first()
            if not account:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Get field name from query params (required)
            field_name = request.query_params.get('field_name')
            if not field_name:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="field_name")
                )
            
            # Get signals for this field
            signals = account.get_related_signals(
                field_name=field_name,
                include_expired=True
            )
            
            # Get field signal metadata if available
            field_metadata = account.get_field_signal_metadata(field_name)
            
            # Prepare response
            result = {
                'field_name': field_name,
                'current_value': getattr(account, field_name, None),
                'metadata': field_metadata
            }
            
            # Add signals by status
            for status, queryset in signals.items():
                if queryset.exists():
                    from apps.sales_insight.serializers import SignalSerializer
                    result[f'{status}_signals'] = SignalSerializer(queryset, many=True).data
                else:
                    result[f'{status}_signals'] = []
            
            return Response(result)
            
        except Exception as exc:
            return self.handle_exception(exc)
    
    def get_hierarchy(self, request, pk=None, *args, **kwargs):
        """Get the full hierarchy for an account"""
        try:
            account = self.get_objects([pk]).first()
            if not account:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
                
            hierarchy = account.get_full_hierarchy()
            
            # Validate all related objects are within client scope
            all_related = hierarchy['parents'] + hierarchy['children']
            for related in all_related:
                self.validate_client_id(related)
            
            return Response({
                "account": self.serializer_class(account).data,
                "parents": self.serializer_class(hierarchy['parents'], many=True).data,
                "children": self.serializer_class(hierarchy['children'], many=True).data,
            })
            
        except Exception as exc:
            return self.handle_exception(exc)
        

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