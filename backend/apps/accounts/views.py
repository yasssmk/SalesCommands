# from rest_framework import viewsets, status
# from rest_framework.response import Response
# from rest_framework.decorators import action
# from rest_framework.exceptions import NotFound
# from .models import Account
# from .serializers import AccountSerializer
# from django.shortcuts import get_object_or_404
# from django.core.exceptions import ValidationError
# from django.views.decorators.csrf import csrf_exempt


# def manage_account_relationship(account, parent=None, remove_parent=False):
#     """Handle parent-child relationship updates for the account."""
#     if parent:
#         # Check for circular relationships
#         if account.id == parent.id or parent in account.direct_child_companies.all():
#             raise ValueError("Circular parent-child relationship detected.")
        
#         # Update account to be a child
#         account.is_child_company = True
#         account.parent_company = parent

#         # Mark the parent as a parent company
#         parent.is_parent_company = True
#         parent.save()

#     elif remove_parent:
#         # Remove parent relationship
#         if account.parent_company:
#             old_parent = account.parent_company
#             account.parent_company = None
#             account.is_child_company = False
#             account.save()

#             # Check if the old parent still has children
#             if not old_parent.direct_child_companies.exists():
#                 old_parent.is_parent_company = False
#                 old_parent.save()

#     account.save()



# # class AccountViewSet(viewsets.ModelViewSet):
# #     queryset = Account.objects.all()
# #     serializer_class = AccountSerializer

# #     # List accounts
# #     @csrf_exempt
# #     def list(self, request, *args, **kwargs):
# #         accounts = self.get_queryset()
# #         serializer = self.get_serializer(accounts, many=True)
# #         return Response(serializer.data)

# #     # Retrieve single account
# #     @csrf_exempt
# #     def retrieve(self, request, *args, **kwargs):
# #         account = self.get_object()
# #         serializer = self.get_serializer(account)
# #         return Response(serializer.data)

# #     # Create a new account
# #     @csrf_exempt
# #     def create(self, request, *args, **kwargs):
# #         serializer = self.get_serializer(data=request.data)
# #         serializer.is_valid(raise_exception=True)
# #         account = serializer.save()

# #         # Manage relationships
# #         parent = account.parent_company
# #         manage_account_relationship(account, parent)

# #         return Response(serializer.data, status=status.HTTP_201_CREATED)

# #     # Update an existing account
# #     @csrf_exempt
# #     def update(self, request, *args, **kwargs):
# #         account = self.get_object()
# #         serializer = self.get_serializer(account, data=request.data, partial=False)
# #         serializer.is_valid(raise_exception=True)
# #         updated_account = serializer.save()

# #         # Manage relationships
# #         parent = updated_account.parent_company
# #         manage_account_relationship(updated_account, parent)

# #         return Response(serializer.data, status=status.HTTP_200_OK)

# #     # Partially update an account
# #     @csrf_exempt
# #     def partial_update(self, request, *args, **kwargs):
# #         account = self.get_object()
# #         serializer = self.get_serializer(account, data=request.data, partial=True)
# #         serializer.is_valid(raise_exception=True)
# #         updated_account = serializer.save()

# #         # Manage relationships
# #         parent = updated_account.parent_company
# #         manage_account_relationship(updated_account, parent)

# #         return Response(serializer.data, status=status.HTTP_200_OK)

# #     # Delete an account
# #     @csrf_exempt
# #     def destroy(self, request, *args, **kwargs):
# #         account = self.get_object()
# #         account.delete()
# #         return Response(status=status.HTTP_204_NO_CONTENT)

# #     # Custom delete endpoint
# #     @csrf_exempt
# #     @action(detail=True, methods=['delete'])
# #     def delete_account(self, request, pk=None):
# #         account = get_object_or_404(Account, pk=pk)
# #         account.delete()
# #         return Response(status=status.HTTP_204_NO_CONTENT)
    

#     # Optionally, add other custom actions here (like assigning account to an owner)
#     # @action(detail=True, methods=['patch'])
#     # def assign_owner(self, request, pk=None):
#     #     account = self.get_object()
#     #     # Custom logic to assign owner
#     #     return Response(status=status.HTTP_200_OK)       


# class AccountViewSet(viewsets.ModelViewSet):
#     queryset = Account.objects.all()
#     serializer_class = AccountSerializer
#     print(queryset)

#     def perform_create(self, serializer):
#         account = serializer.save()
#         parent = serializer.validated_data.get('parent_company')
#         if parent:
#             manage_account_relationship(account, parent=parent)
        

#     def perform_update(self, serializer):
#         account = self.get_object()
#         parent = serializer.validated_data.get('parent_company')
#         # print(f"Yo: {queryset}")
#         if parent:
#             manage_account_relationship(account, parent=parent)
#         elif 'parent_company' in serializer.validated_data and not serializer.validated_data['parent_company']:
#             manage_account_relationship(account, remove_parent=True)

#     def destroy(self, request, *args, **kwargs):
#         account = self.get_object()
#         manage_account_relationship(account, remove_parent=True)
#         account.delete()

#     # Optionally, add other custom actions here (like assigning account to an owner)
#     # @action(detail=True, methods=['patch'])
#     # def assign_owner(self, request, pk=None):
#     #     account = self.get_object()
#     #     # Custom logic to assign owner
#     #     return Response(status=status.HTTP_200_OK)

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
    
    # Optional: Add authentication
    # permission_classes = [IsAuthenticated]
    
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