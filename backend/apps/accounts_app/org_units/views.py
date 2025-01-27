from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from django.core.exceptions import ValidationError
from rest_framework.exceptions import AuthenticationFailed
from django.db import transaction
from core.apps_shared_methods import BaseAPIView
from .models import AccountOrganizationUnit
from .serializers import AccountOrganizationUnitSerializer
from django.utils.translation import gettext_lazy as _
from core.error_messages import CoreErrorMessages, AccountErrorMessages
from datetime import datetime

class AccountOrganizationUnitAPIView(BaseAPIView):
    """
    API View for AccountOrganizationUnit management with parent-child relationship handling.
    """
    
    queryset = AccountOrganizationUnit.objects.select_related(
        'account',
        'parent_organization_unit',
        'org_insights'
    ).prefetch_related('child_organization_units')
    
    serializer_class = AccountOrganizationUnitSerializer
    entity_name = 'organization_unit'

    mass_update_allowed_fields = {'unit_type', 'estimated_employee_count'}

    def get_queryset(self):
        """Extend base queryset with organization unit-specific filtering"""
        try:
            queryset = super().get_queryset()
            
            filter_mappings = {
                'account_id': 'account_id',
                'parent_ids': 'parent_organization_unit_id__in',
                'unit_types': 'unit_type__in'
            }
            
            for param, field in filter_mappings.items():
                values = self.request.query_params.get(param)
                if values:
                    if param == 'account_id':
                        queryset = queryset.filter(**{field: values.strip()})
                    else:
                        filter_list = [v.strip() for v in values.split(',')]
                        queryset = queryset.filter(**{field: filter_list})
                        
            return queryset
                
        except ValueError:
            raise ValidationError({
                'error': CoreErrorMessages.INVALID_FILTER,
                'detail': f"Invalid format for filter parameters: {', '.join(filter_mappings.keys())}"
            })

    def _validate_parent_unit(self, parent_id, account_id, client_id):
        """Validate parent organization unit exists and belongs to same account and client"""
        if parent_id:
            try:
                parent = AccountOrganizationUnit.objects.get(id=parent_id)
                if str(parent.client_id) != str(client_id):
                    raise ValidationError({
                        'parent_id': AccountErrorMessages.INVALID_PARENT
                    })
                if str(parent.account_id) != str(account_id):
                    raise ValidationError({
                        'parent_id': AccountErrorMessages.INVALID_PARENT_ORG
                    })
                return parent
            except AccountOrganizationUnit.DoesNotExist:
                raise ValidationError({
                    'parent_id': AccountErrorMessages.PARENT_NOT_FOUND
                })
        return None

    def _update_instance(self, instance, data, partial, client_id):
        """Optimized update with minimal queries"""
        try:
            self.validate_client_id(instance)
            
            # Track fields that need refresh
            refresh_fields = set()
            
            # Store old values for relationship changes
            old_parent = instance.parent_organization_unit_id
            old_account = instance.account_id
            
            serializer = self.serializer_class(
                instance,
                data=data,
                partial=partial,
                context={'request': self.request, 'client_id': client_id}
            )
            
            if serializer.is_valid():
                with transaction.atomic():
                    # Prevent changing account
                    if 'account' in data and str(data['account']) != str(old_account):
                        raise ValidationError(AccountErrorMessages.CHANGE_ACCOUNT_ORG)
                    
                    updated = serializer.save()
                    
                    # Only refresh changed relationships
                    if old_parent != updated.parent_organization_unit_id:
                        refresh_fields.add('parent_organization_unit')
                        if old_parent:
                            AccountOrganizationUnit.objects.filter(id=old_parent).update(
                                updated_at=datetime.now()
                            )
                    
                    if refresh_fields:
                        updated.refresh_from_db(fields=refresh_fields)
                    
                    return serializer
                    
            raise ValidationError(serializer.errors)
        except ValidationError as e:
            raise ValidationError(e)

    @action(detail=True, methods=['get'])
    def hierarchy(self, request, pk=None):
        """Get the full hierarchy for an organization unit"""
        try:
            objects = self.get_objects()
            if not objects or objects.count() != 1:
                raise ValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
                
            instance = objects[0]
            
            # Build hierarchy
            hierarchy = {
                'parents': [],
                'children': list(instance.child_organization_units.all())
            }
            
            # Get parent hierarchy
            current = instance
            while current.parent_organization_unit:
                hierarchy['parents'].append(current.parent_organization_unit)
                current = current.parent_organization_unit
            
            # Validate all related objects are within client scope
            all_related = hierarchy['parents'] + hierarchy['children']
            for related in all_related:
                self.validate_client_id(related)
            
            return Response({
                "organization_unit": self.serializer_class(instance).data,
                "parents": self.serializer_class(hierarchy['parents'], many=True).data,
                "children": self.serializer_class(hierarchy['children'], many=True).data,
            })
            
        except Exception as exc:
            return self.handle_exception(exc)


class OrganizationUnitChoicesView(APIView):
    """
    API endpoint for retrieving organization unit type choices.
    No client scoping needed as these are global choices.
    """
    def get(self, request):
        return Response({
            'unit_types': [
                {'value': choice[0], 'label': choice[1]} 
                for choice in AccountOrganizationUnit.UnitType.choices
            ]
        })