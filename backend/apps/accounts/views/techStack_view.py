# apps/accounts/views/techstack_view.py

from django.db.models import Q
from core.apps_shared_methods import BaseAPIView
from apps.core_apps.views import SignalAwareViewMixin, TechStackHistoricalTrackingMixin
from ..models import TechStack
from ..serializers import TechStackSerializer
from django.utils.translation import gettext_lazy as _


class TechStackAPIView(BaseAPIView, TechStackHistoricalTrackingMixin, SignalAwareViewMixin ):
    """
    API View for TechStack management with historical tracking.
    """
    
    queryset = TechStack.objects.select_related('account')
    serializer_class = TechStackSerializer
    entity_name = 'techstack'

    mass_update_allowed_fields = {'tech_name', 'purpose', 'annual_cost', 'renewal_date'}

    def get_queryset(self):
        """Extend base queryset with tech stack-specific filtering"""

        queryset = super().get_queryset()
            
        filter_mappings = {
            'account_id': 'account_id',
            'tech_name': 'tech_name__icontains',
            'search': None  # Special handling for search
        }
            
        for param, field in filter_mappings.items():
            values = self.request.query_params.get(param)
            if values and field:
                queryset = queryset.filter(**{field: values.strip()})
            elif param == 'search' and values:
                search_term = values.strip()
                queryset = queryset.filter(
                Q(tech_name__icontains=search_term) | 
                Q(purpose__icontains=search_term)
                )
                    
        return queryset
                
