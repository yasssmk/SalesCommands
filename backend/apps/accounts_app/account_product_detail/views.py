from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, F, Value, DecimalField
from django.db.models.functions import Coalesce
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from core.views import BaseAPIView
from apps.accounts_app.accounts.models import Account
from .models import AccountProductDetail
from .serializers import AccountProductDetailSerializer
from decimal import Decimal

class AccountProductDetailView(BaseAPIView):
    """
    ViewSet for managing AccountProductDetail instances.
    Supports standard CRUD operations with client scoping.
    """
    queryset = AccountProductDetail.objects.all()
    serializer_class = AccountProductDetailSerializer
    entity_name = 'account_product_detail'

    def get_account(self):
        """Get the account object and validate client scope."""
        account_id = self.kwargs.get('account_id')
        if not account_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(
                    field="Account ID is required"
                )
            )
            
        try:
            account = Account.objects.get(id=account_id)
            # Validate client scope
            self.validate_client_id(account)
            return account
        except Account.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

    def get_serializer_context(self):
        """Add account to serializer context."""
        context = super().get_serializer_context()
        context['account'] = self.get_account()
        return context

    def get_queryset(self):
        """Get base queryset with account and client filtering."""
        queryset = super().get_queryset()
        account = self.get_account()
        return self.filter_queryset_by_client(
            queryset.filter(account=account)
        )

    @action(detail=False, methods=['get'])
    def summary(self, request, account_id=None):
        """
        Get revenue summary for the account grouped by revenue type.
        """
        queryset = self.get_queryset()
        
        summary = {
            'MRR': Decimal('0.00'),
            'QRR': Decimal('0.00'),
            'ARR': Decimal('0.00'),
            'ONE_TIME': Decimal('0.00'),
            'total_products': 0
        }
        
        # Aggregate revenue by type
        revenue_summary = queryset.values('revenue_type').annotate(
            total=Coalesce(Sum('potential_revenue'), Value(0, output_field=DecimalField()))
        )
        
        for item in revenue_summary:
            summary[item['revenue_type']] = item['total']
        
        summary['total_products'] = queryset.count()
        
        return Response(summary)

    @action(detail=False, methods=['get'])
    def whitespace(self, request, account_id=None):
        """
        Get whitespace analysis for products not yet analyzed for the account.
        """
        account = self.get_account()
        client_id = self.get_client_id()
        
        # Get all client's products
        from apps.products.models import Product
        all_products = Product.objects.filter(client_id=client_id)
        
        # Get products already analyzed
        analyzed_products = self.get_queryset().values_list('product_id', flat=True)
        
        # Get products not yet analyzed
        whitespace_products = all_products.exclude(id__in=analyzed_products)
        
        from apps.products.serializers import ProductSerializer
        serializer = ProductSerializer(whitespace_products, many=True)
        
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        """Create account product detail(s)."""
        account = self.get_account()
        client_id = self.get_client_id()

        # Handle bulk creation
        if isinstance(request.data, list):
            created_objects = []
            for item in request.data:
                serializer = self.serializer_class(
                    data=item,
                    context={
                        'request': request,
                        'account': account,
                        'client_id': client_id
                    }
                )
                serializer.is_valid(raise_exception=True)
                instance = serializer.save()
                created_objects.append(instance)

            response_serializer = self.serializer_class(created_objects, many=True)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        # Single object creation
        serializer = self.serializer_class(
            data=request.data,
            context={
                'request': request,
                'account': account,
                'client_id': client_id
            }
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(
            self.serializer_class(instance).data,
            status=status.HTTP_201_CREATED
        )

    def patch(self, request, *args, **kwargs):
        """Update account product detail(s)."""
        account = self.get_account()
        client_id = self.get_client_id()

        # Handle bulk updates
        detail_ids = request.query_params.get(f'{self.entity_name}_ids')
        if detail_ids:
            ids = [id_.strip() for id_ in detail_ids.split(',') if id_.strip()]
            if not ids:
                raise StandardizedValidationError(CoreErrorMessages.NO_OBJECTS_FOUND)

            objects = self.get_objects(ids)
            updated_objects = []

            for obj in objects:
                serializer = self.serializer_class(
                    obj,
                    data=request.data,
                    partial=True,
                    context={
                        'request': request,
                        'account': account,
                        'client_id': client_id
                    }
                )
                serializer.is_valid(raise_exception=True)
                updated = serializer.save()
                updated_objects.append(updated)

            return Response(
                self.serializer_class(updated_objects, many=True).data
            )

        # Single object update
        instance = self.get_objects().first()
        if not instance:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

        serializer = self.serializer_class(
            instance,
            data=request.data,
            partial=True,
            context={
                'request': request,
                'account': account,
                'client_id': client_id
            }
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(self.serializer_class(updated).data)

    def delete(self, request, *args, **kwargs):
        """Delete account product detail(s)."""
        return super().delete(request, *args, **kwargs)