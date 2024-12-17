from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from .models import Account
from .serializer import AccountSerializer
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()  # Retrieve all accounts
    serializer_class = AccountSerializer

    # List accounts
    def list(self, request, *args, **kwargs):
        accounts = self.get_queryset()
        serializer = self.get_serializer(accounts, many=True)
        return Response(serializer.data)

    # Retrieve single account
    def retrieve(self, request, *args, **kwargs):
        account = self.get_object()
        serializer = self.get_serializer(account)
        return Response(serializer.data)

    # Create a new account
    @csrf_exempt
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # Update an existing account
    def update(self, request, *args, **kwargs):
        account = self.get_object()
        serializer = self.get_serializer(account, data=request.data, partial=False)  # partial=False for full update
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    # Partially update an account
    def partial_update(self, request, *args, **kwargs):
        account = self.get_object()
        serializer = self.get_serializer(account, data=request.data, partial=True)  # partial=True for partial update
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    # Delete an account
    def destroy(self, request, *args, **kwargs):
        account = self.get_object()
        account.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # Custom action to handle deletion by account ID (if needed)
    @action(detail=True, methods=['delete'])
    def delete_account(self, request, pk=None):
        account = self.get_object()
        account.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # Optionally, add other custom actions here (like assigning account to an owner)
    # @action(detail=True, methods=['patch'])
    # def assign_owner(self, request, pk=None):
    #     account = self.get_object()
    #     # Custom logic to assign owner
    #     return Response(status=status.HTTP_200_OK)       
