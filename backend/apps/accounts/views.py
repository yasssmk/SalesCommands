from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db import transaction
from rest_framework.decorators import action
import logging
from django.http import JsonResponse

from .models import Account
from .serializers import AccountSerializer
from django.shortcuts import get_object_or_404
from django.core.cache import cache


class AccountAPIView(views.APIView):
    """
    API for managing accounts with CRUD functionality.
    """

    queryset = Account.objects.prefetch_related('direct_child_companies')
    serializer_class = AccountSerializer

    # filter_backends = [
    #     DjangoFilterBackend,
    #     filters.SearchFilter,
    #     filters.OrderingFilter,
    # ]
    # filterset_fields = ['type', 'classification', 'country']
    # search_fields = ['company_name', 'industry']
    # ordering_fields = ['created_at', 'number_of_employees', 'potential']

    def handle_exception(self, exc):
        """
        Log and handle unexpected exceptions.
        """
        # logger.error(f"Exception: {str(exc)}", exc_info=True)
        return Response({
            "status": "error",
            "message": "An unexpected error occurred",
            "error": str(exc),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request, pk=None, *args, **kwargs):
        """
        Handle READ ALL or READ by account ID.
        """
        # cache_key = f"account_{pk}" if pk else "accounts_list"
        # cached_data = cache.get(cache_key)

        # if cached_data:
        #     return Response(cached_data, status=status.HTTP_200_OK)

        if pk:
            instance = get_object_or_404(self.queryset.all(), pk=pk)
            serializer = self.serializer_class(instance)
            data = serializer.data

        else:
            account_ids = request.query_params.getlist('account_ids', None)
            queryset = self.queryset.all() 
            if account_ids:
                queryset = queryset.filter(id__in=account_ids)
            serializer = self.serializer_class(queryset, many=True)
            data = serializer.data

        # cache.set(cache_key, data, timeout=60 * 60) #1 hour

        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        """
        Handle CREATE operation.
        """
        print(request.data)
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                self.perform_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk=None, *args, **kwargs):
        """
        Handle UPDATE operation by ID.
        """
        instance = get_object_or_404(self.queryset.all(), pk=pk) 
        serializer = self.serializer_class(instance, data=request.data, partial=False)
        if serializer.is_valid():
            with transaction.atomic():
                self.perform_update(serializer)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None, *args, **kwargs):
        """
        Handle DELETE operation by ID.
        """
        instance = get_object_or_404(self.queryset.all(), pk=pk)  
        with transaction.atomic():
            instance.delete()
        return Response({"message": "Record deleted successfully."}, status=status.HTTP_202_ACCEPTED)

    def perform_create(self, serializer):
        parent = serializer.validated_data.get('parent_company')
        account = serializer.save()
        if parent:
            account.parent_company = parent
            account.save()

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = serializer.instance
            old_parent = instance.parent_company
            instance = serializer.save()
            new_parent = serializer.validated_data.get('parent_company')

            if old_parent != new_parent:
                if old_parent and not old_parent.direct_child_companies.exclude(id=instance.id).exists():
                    old_parent.save()
                if new_parent:
                    new_parent.save()

    # def hierarchy(self, request, *args, **kwargs):
    #     account = self.get_object()
    #     hierarchy = account.get_full_hierarchy()
    #     return Response({
    #         "account": self.serializer_class(account).data,
    #         "parents": self.serializer_class(hierarchy['parents'], many=True).data,
    #         "children": self.serializer_class(hierarchy['children'], many=True).data,
    #     }, status=status.HTTP_200_OK)

    def get_object(self):
        """
        Retrieve single object based on primary key.
        """
        pk = self.kwargs.get('pk')
        return get_object_or_404(self.queryset.all(), pk=pk)


# Views for exposing choices
def get_account_choices(request):
    return JsonResponse({
        'types': Account.get_account_types(),
        'classifications': Account.get_account_classifications()
    })
