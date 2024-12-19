from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db import transaction

from .models import Account
from .serializers import AccountSerializer

class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.prefetch_related('direct_child_companies')
    serializer_class = AccountSerializer
    
    # TO DO: Add authentication, permission by Role and injection valaidation
    # permission_classes = [IsAuthenticated]
    # Content_Validation = [IsContentValidated]
    
    # Add filtering and search capabilities
    filter_backends = [
        DjangoFilterBackend, 
        filters.SearchFilter, 
        filters.OrderingFilter
    ]
    filterset_fields = ['type', 'classification', 'country']
    search_fields = ['company_name', 'industry']
    ordering_fields = ['created_at', 'number_of_employees', 'potential']

    @action(detail=True, methods=['GET'])
    def hierarchy(self, request, pk=None):
        """
        Custom action to retrieve full company hierarchy
        """
        account = self.get_object()
        hierarchy = account.get_full_hierarchy()
        
        return Response({
            'account': self.get_serializer(account).data,
            'parents': self.get_serializer(hierarchy['parents'], many=True).data,
            'children': self.get_serializer(hierarchy['children'], many=True).data
        })

    def perform_create(self, serializer):
        """
        Handle parent-child relationship during creation
        """
        parent = serializer.validated_data.get('parent_company')
        account = serializer.save()
        
        if parent:
            account.parent_company = parent
            account.save()

    def perform_update(self, serializer):
        """
        Handle parent-child relationship updates
        """
        with transaction.atomic():
            instance = self.get_object()
            old_parent = instance.parent_company
            
            # Save the instance with any updated fields
            instance = serializer.save()
            
            # Get the new parent from validated data
            new_parent = serializer.validated_data.get('parent_company')
            
            # Handle parent company changes
            if old_parent != new_parent:
                if old_parent and not old_parent.direct_child_companies.exclude(id=instance.id).exists():
                    # If old parent has no other children, update its status
                    old_parent.save()
                
                if new_parent:
                    # Update the new parent if needed
                    new_parent.save()