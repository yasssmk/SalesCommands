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

    @action(detail=True, methods=['get'])
    def hierarchy(self, request, pk=None):
        """Get the full hierarchy for an account"""
        try:
            objects = self.get_objects()
            if not objects or objects.count() != 1:
                raise ValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
                
            instance = objects[0]
            hierarchy = instance.get_full_hierarchy()
            
            # Validate all related objects are within client scope
            all_related = hierarchy['parents'] + hierarchy['children']
            for related in all_related:
                self.validate_client_id(related)
            
            return Response({
                "account": self.serializer_class(instance).data,
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