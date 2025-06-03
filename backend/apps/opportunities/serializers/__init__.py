# apps/opportunities/serializers/__init__.py

# Import core opportunity serializers
from .opportunity_serializer import (
    OpportunitySerializer,
    OpportunityListSerializer
)

# Import financial serializers
from .opportunity_financial_serializer import (
    OpportunityLineItemSerializer,
    OpportunityFinancialSummarySerializer,
    OpportunityWithFinancialsSerializer
)

# Import tracking serializers
from .opportunity_tracking_serializer import (
    OpportunitySourceSerializer,
    OpportunityActivitySerializer,
    OpportunityHistorySerializer,
    LeadConversionSerializer
)

# Export all serializers
__all__ = [
    # Core opportunity
    'OpportunitySerializer',
    'OpportunityListSerializer',
    
    # Financial
    'OpportunityLineItemSerializer',
    'OpportunityFinancialSummarySerializer',
    'OpportunityWithFinancialsSerializer',
    
    # Tracking
    'OpportunitySourceSerializer',
    'OpportunityActivitySerializer',
    'OpportunityHistorySerializer',
    'LeadConversionSerializer',
]