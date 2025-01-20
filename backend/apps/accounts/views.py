# apps/accounts/views.py
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.core.exceptions import ValidationError
from django.db import transaction
from core.apps_shared_methods import BaseAPIView
from .models import Account
from .serializers import AccountSerializer
from django.utils.translation import gettext_lazy as _


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

    def get_queryset(self):
        """Extend base queryset with account-specific filtering"""
        queryset = super().get_queryset()
        
        # Handle list-based filters
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
                    
        except ValueError as e:
            raise ValidationError(_("Invalid filter format provided"))
            
        return queryset

    def _validate_parent_company(self, parent_id, client_id):
        """Validate parent company exists and belongs to same client"""
        if parent_id:
            try:
                parent = Account.objects.get(id=parent_id)
                if str(parent.client_id) != str(client_id):
                    raise ValidationError(_("Invalid parent company assignment"))
                return parent
            except Account.DoesNotExist:
                raise ValidationError(_("Parent company not found"))
        return None

    def _update_instance(self, instance, data, partial, client_id):
        """Override to handle parent-child relationship updates"""
        self.validate_client_id(instance)
        
        # Store old parent for relationship handling
        old_parent = instance.parent_company
        
        # Handle parent_id if present in the data
        parent_id = data.get('parent_id')
        if parent_id is not None:
            new_parent = self._validate_parent_company(parent_id, client_id)
            # Update the data with the validated parent
            data['parent_company'] = parent_id
        
        serializer = self.serializer_class(
            instance,
            data=data,
            partial=partial,
            context={'request': self.request, 'client_id': client_id}
        )
        
        if serializer.is_valid():
            with transaction.atomic():
                updated = serializer.save()
                
                # Handle parent-child relationship updates if needed
                new_parent = updated.parent_company
                if old_parent != new_parent:
                    if old_parent and not old_parent.direct_child_companies.exclude(
                        id=instance.id
                    ).exists():
                        old_parent.save()
                    if new_parent:
                        new_parent.save()
        else:
            raise ValidationError(serializer.errors)
            
        return serializer

    @action(detail=True, methods=['get'])
    def hierarchy(self, request, pk=None):
        """Get the full hierarchy for an account"""
        try:
            # Get the account instance
            objects = self.get_objects()
            if not objects or objects.count() != 1:
                raise ValidationError(_("Account not found"))
                
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