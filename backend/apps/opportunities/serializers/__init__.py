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

# Pipeline Serializers
from .pipeline_template_serializer import PipelineTemplateSerializer
from .pipeline_stage_serializer import PipelineStageSerializer
from .pipeline_substage_serializer import PipelineSubStageSerializer
from .substage_metadata_serializer import SubStageMetadataSerializer
from .opportunity_pipeline_serializer import OpportunityPipelineSerializer
from .substage_activity_serializer import SubStageActivitySerializer

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

    # Pipeline Serializers
    'PipelineTemplateSerializer',
    'PipelineStageSerializer',
    'PipelineSubStageSerializer',
    'SubStageMetadataSerializer',
    'OpportunityPipelineSerializer',
    'SubStageActivitySerializer'
]