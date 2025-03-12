
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import  Q
from core.apps_shared_methods import BaseAPIView
from ..models import Competitor
from ..serializers import CompetitorSerializer, ProductSummarySerializer
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError


class CompetitorAPIView(BaseAPIView):
    queryset = Competitor.objects.all()
    serializer_class = CompetitorSerializer
    entity_name = 'competitor'
    mass_update_allowed_fields = {'description', 'website', 'battle_cards', 'product_ids'}
    
    def get_queryset(self):
        """Get filtered and optimized queryset"""
        queryset = super().get_queryset()
        
        filters = {}
        
        # Filter by product
        product_id = self.request.query_params.get('product_id')
        if product_id:
            filters['products__id'] = product_id
            
        # Text search
        search = self.request.query_params.get('search')
        if search:
            filters['Q'] = Q(name__icontains=search) | Q(description__icontains=search)
            
        # Apply filters
        if filters:
            if 'Q' in filters:
                q_filter = filters.pop('Q')
                queryset = queryset.filter(q_filter)
            queryset = queryset.filter(**filters)
            
        # Optimize queries
        return queryset.prefetch_related(
            'products'
        ).select_related(
            'created_by',
            'updated_by'
        ).distinct()
        
    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Get products associated with this competitor"""
        competitor = self.get_object()
        products = competitor.products.all()
        serializer = ProductSummarySerializer(products, many=True)
        return Response(serializer.data)
        
    @action(detail=False, methods=['get'])
    def battle_cards(self, request):
        """Get battle cards for a specific product against competitors"""
        product_id = request.query_params.get('product_id')
        if not product_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="product_id")
            )
            
        competitors = self.get_queryset().filter(products__id=product_id)
        results = []
        
        for competitor in competitors:
            results.append({
                'id': competitor.id,
                'name': competitor.name,
                'battle_cards': competitor.battle_cards
            })
            
        return Response(results)