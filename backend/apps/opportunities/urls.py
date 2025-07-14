# apps/opportunities/urls.py

from django.urls import path
from .views.opportunity_views import OpportunityViewSet
from .views.opportunity_financial_views import OpportunityLineItemViewSet, OpportunityFinancialSummaryViewSet
from .views.opportunity_tracking_views import OpportunitySourceViewSet, OpportunityActivityViewSet
from .views.pipeline_template_views import PipelineTemplateViewSet
from apps.campaign.views.campaign_views import CampaignViewSet
from .views.pipeline_views import PipelineViewSet

urlpatterns = [
    # Opportunity CRUD operations
    path('', OpportunityViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='opportunity-list-create'),
    
    path('<int:pk>/', OpportunityViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='opportunity-detail'),
    
    # Custom opportunity actions
    path('<int:pk>/with-financials/', OpportunityViewSet.as_view({
        'get': 'with_financials'
    }), name='opportunity-with-financials'),
    
    path('<int:pk>/mark-as-won/', OpportunityViewSet.as_view({
        'post': 'mark_as_won'
    }), name='opportunity-mark-as-won'),
    
    path('<int:pk>/mark-as-lost/', OpportunityViewSet.as_view({
        'post': 'mark_as_lost'
    }), name='opportunity-mark-as-lost'),
    
    path('<int:pk>/assign/', OpportunityViewSet.as_view({
        'post': 'assign'
    }), name='opportunity-assign'),
    
    path('<int:pk>/history/', OpportunityViewSet.as_view({
        'get': 'history'
    }), name='opportunity-history'),
    
    # Opportunity collections
    path('convert-lead/', OpportunityViewSet.as_view({
        'post': 'convert_lead'
    }), name='opportunity-convert-lead'),
    
    path('summary/', OpportunityViewSet.as_view({
        'get': 'summary'
    }), name='opportunity-summary'),
    
    # Opportunity Line Items CRUD operations
    path('line-items/', OpportunityLineItemViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='line-item-list-create'),
    
    path('line-items/<int:pk>/', OpportunityLineItemViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='line-item-detail'),
    
    # Line Items collections
    path('line-items/available-products/', OpportunityLineItemViewSet.as_view({
        'get': 'available_products'
    }), name='line-item-available-products'),
    
    # Financial Summaries CRUD operations
    path('financials/', OpportunityFinancialSummaryViewSet.as_view({
        'get': 'list'
    }), name='financial-summary-list'),
    
    path('financials/<int:pk>/', OpportunityFinancialSummaryViewSet.as_view({
        'get': 'retrieve',
        'patch': 'partial_update'
    }), name='financial-summary-detail'),
    
    # Financial Summaries collections
    path('financials/forecast/', OpportunityFinancialSummaryViewSet.as_view({
        'get': 'forecast'
    }), name='financial-summary-forecast'),
    
    # Opportunity Sources CRUD operations
    path('sources/', OpportunitySourceViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='opportunity-source-list-create'),
    
    path('sources/<int:pk>/', OpportunitySourceViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='opportunity-source-detail'),
    
    # Custom source actions
    path('sources/<int:pk>/accept-conversion/', OpportunitySourceViewSet.as_view({
        'post': 'accept_conversion'
    }), name='opportunity-source-accept'),
    
    path('sources/<int:pk>/reject-conversion/', OpportunitySourceViewSet.as_view({
        'post': 'reject_conversion'
    }), name='opportunity-source-reject'),
    
    # Opportunity Activities CRUD operations
    path('activities/', OpportunityActivityViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='opportunity-activity-list-create'),
    
    path('activities/<int:pk>/', OpportunityActivityViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='opportunity-activity-detail'),
    
    # Custom activity actions
    path('activities/create-activity/', OpportunityActivityViewSet.as_view({
        'post': 'create_activity'
    }), name='opportunity-activity-create'),
    
    path('activities/opportunity-timeline/', OpportunityActivityViewSet.as_view({
        'get': 'opportunity_timeline'
    }), name='opportunity-activity-timeline'),

    # =========================================================================
    # PIPELINE TEMPLATES - Gestion des templates et de leurs stages
    # =========================================================================
    
    # Pipeline Templates CRUD operations
    path('pipeline-templates/', PipelineTemplateViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='pipeline-template-list-create'),
    
    path('pipeline-templates/<int:pk>/', PipelineTemplateViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='pipeline-template-detail'),
    
    # Pipeline Template collections
    path('pipeline-templates/choices/', PipelineTemplateViewSet.as_view({
        'get': 'choices'
    }), name='pipeline-template-choices'),
    
    # Pipeline Template actions
    path('pipeline-templates/<int:pk>/duplicate/', PipelineTemplateViewSet.as_view({
        'post': 'duplicate'
    }), name='pipeline-template-duplicate'),
    
    path('pipeline-templates/<int:pk>/set-as-default/', PipelineTemplateViewSet.as_view({
        'post': 'set_as_default'
    }), name='pipeline-template-set-default'),
    
    # Pipeline Template Stages management
    path('pipeline-templates/<int:pk>/stages/', PipelineTemplateViewSet.as_view({
        'get': 'list_stages',
        'post': 'add_stage'
    }), name='pipeline-template-stages'),
    
    path('pipeline-templates/<int:pk>/stages/<int:stage_id>/', PipelineTemplateViewSet.as_view({
        'put': 'update_stage',
        'delete': 'remove_stage'
    }), name='pipeline-template-stage-detail'),

    # =========================================================================
    # OPPORTUNITY PIPELINES - Gestion des pipelines d'opportunité et substages
    # =========================================================================
    
    # Pipeline Management - Core operations
    path('<int:opportunity_id>/pipeline/', PipelineViewSet.as_view({
        'get': 'retrieve_pipeline',
        'put': 'update_pipeline'
    }), name='opportunity-pipeline-detail'),
    
    path('<int:opportunity_id>/pipeline/initialize/', PipelineViewSet.as_view({
        'post': 'initialize_pipeline'
    }), name='opportunity-pipeline-initialize'),
    
    path('<int:opportunity_id>/pipeline/overview/', PipelineViewSet.as_view({
        'get': 'pipeline_overview'
    }), name='opportunity-pipeline-overview'),
    
    # SubStages Management
    path('<int:opportunity_id>/pipeline/substages/', PipelineViewSet.as_view({
        'get': 'list_substages',
        'post': 'add_substage'
    }), name='opportunity-pipeline-substages'),
    
    path('<int:opportunity_id>/pipeline/substages/<int:substage_id>/', PipelineViewSet.as_view({
        'put': 'update_substage',
        'delete': 'remove_substage'
    }), name='opportunity-pipeline-substage-detail'),
    
    # SubStage Status Management
    path('<int:opportunity_id>/pipeline/substages/<int:substage_id>/start/', PipelineViewSet.as_view({
        'post': 'start_substage'
    }), name='opportunity-pipeline-substage-start'),
    
    path('<int:opportunity_id>/pipeline/substages/<int:substage_id>/complete/', PipelineViewSet.as_view({
        'post': 'complete_substage'
    }), name='opportunity-pipeline-substage-complete'),
    
    # =========================================================================
    # INTÉGRATION FOLLOW-UP - Via SubStageFollowUpService
    # =========================================================================
    
    # Campaign Integration (via SubStageFollowUpService)
    path('<int:opportunity_id>/pipeline/substages/<int:substage_id>/campaigns/', PipelineViewSet.as_view({
        'get': 'list_substage_campaigns'
    }), name='opportunity-pipeline-substage-campaigns'),
    
    path('<int:opportunity_id>/pipeline/substages/<int:substage_id>/add-to-followup/', PipelineViewSet.as_view({
        'post': 'add_substage_to_followup'
    }), name='opportunity-pipeline-substage-add-followup'),
    
    path('<int:opportunity_id>/pipeline/substages/<int:substage_id>/remove-from-followup/', PipelineViewSet.as_view({
        'delete': 'remove_substage_from_followup'
    }), name='opportunity-pipeline-substage-remove-followup'),
    
    path('<int:opportunity_id>/pipeline/substages/<int:substage_id>/complete-followup/', PipelineViewSet.as_view({
        'post': 'complete_substage_followup'
    }), name='opportunity-pipeline-substage-complete-followup'),
    
    path('<int:opportunity_id>/pipeline/substages/<int:substage_id>/followup-status/', PipelineViewSet.as_view({
        'get': 'get_substage_followup_status'
    }), name='opportunity-pipeline-substage-followup-status'),
    
    # Pipeline Activities
    path('<int:opportunity_id>/pipeline/activities/', PipelineViewSet.as_view({
        'get': 'pipeline_activities'
    }), name='opportunity-pipeline-activities'),
]