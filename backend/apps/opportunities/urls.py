# apps/opportunities/urls.py

from django.urls import path
from .views.opportunity_views import OpportunityViewSet
from .views.opportunity_financial_views import OpportunityLineItemViewSet, OpportunityFinancialSummaryViewSet
from .views.opportunity_tracking_views import OpportunitySourceViewSet, OpportunityActivityViewSet
from .views.pipeline_template_views import PipelineTemplateViewSet
from apps.campaign.views.campaign_views import CampaignViewSet
from .views.buying_process_view import BuyingProcessViewSet

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
    # BUYING PROCESSES - Gestion des process de vente et de leurs stages
    # =========================================================================
    
    # ✅ Buying Process CRUD operations (renommé de pipeline-templates)
    path('buying-processes/', BuyingProcessViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='buying-process-list-create'),
    
    path('buying-processes/<int:pk>/', BuyingProcessViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='buying-process-detail'),
    
    # ✅ Buying Process Stages management
    path('buying-processes/<int:pk>/stages/', BuyingProcessViewSet.as_view({
        'get': 'list_stages',
        'post': 'add_stage'
    }), name='buying-process-stages'),
    
    path('buying-processes/<int:pk>/stages/<int:stage_id>/', BuyingProcessViewSet.as_view({
        'patch': 'update_stage',
        'delete': 'remove_stage'
    }), name='buying-process-stage-detail'),

    # ✅ Buying Process SubStages management
    path('buying-processes/<int:pk>/stages/<int:stage_id>/substages/', BuyingProcessViewSet.as_view({
        'get': 'list_substages',
        'post': 'add_substage'
    }), name='buying-process-substages'),
    
    path('buying-processes/<int:pk>/stages/<int:stage_id>/substages/<int:substage_id>/', BuyingProcessViewSet.as_view({
        'patch': 'update_substage',
        'delete': 'remove_substage'
    }), name='buying-process-substage-detail'),

    # ✅ Opportunity Process Overview (functionality preserved)
    path('buying-processes/opportunity/<int:opportunity_id>/overview/', BuyingProcessViewSet.as_view({
        'get': 'opportunity_overview'
    }), name='buying-process-opportunity-overview'),

    # =========================================================================
    # SUBSTAGE ACTIVITIES - Gestion des activités liées aux substages
    # =========================================================================
    
    # ✅ Link existing activity to substage
    path('buying-processes/opportunity/<int:opportunity_id>/substages/<int:substage_id>/link-activity/', BuyingProcessViewSet.as_view({
        'post': 'link_activity_to_substage'
    }), name='buying-process-substage-link-activity'),
    
    # ✅ Create new activity for substage
    path('buying-processes/opportunity/<int:opportunity_id>/substages/<int:substage_id>/create-activity/', BuyingProcessViewSet.as_view({
        'post': 'create_activity_for_substage'
    }), name='buying-process-substage-create-activity'),
    
    # ✅ Unlink activity from substage
    path('buying-processes/opportunity/<int:opportunity_id>/substages/<int:substage_id>/activities/<int:activity_id>/', BuyingProcessViewSet.as_view({
        'delete': 'unlink_activity_from_substage'
    }), name='buying-process-substage-unlink-activity'),
    
    # ✅ Get substage activities timeline
    path('buying-processes/opportunity/<int:opportunity_id>/substages/<int:substage_id>/timeline/', BuyingProcessViewSet.as_view({
        'get': 'get_substage_timeline'
    }), name='buying-process-substage-timeline'),

    # =========================================================================
    # SUBSTAGE FOLLOW-UP MANAGEMENT - Gestion des substages dans les campaigns
    # =========================================================================

    # ✅ CRUD Follow-up : Lister toutes les campaigns d'un substage
    path('buying-processes/opportunity/<int:opportunity_id>/substages/<int:substage_id>/campaigns/', 
        BuyingProcessViewSet.as_view({
            'get': 'list_substage_campaigns'
        }), 
        name='buying-process-substage-campaigns'),

    # ✅ CRUD Follow-up : Ajouter un substage à la campaign follow-up
    path('buying-processes/opportunity/<int:opportunity_id>/substages/<int:substage_id>/add-to-followup/', 
        BuyingProcessViewSet.as_view({
            'post': 'add_substage_to_followup'
        }), 
        name='buying-process-substage-add-followup'),

    # ✅ CRUD Follow-up : Retirer un substage de la campaign follow-up
    path('buying-processes/opportunity/<int:opportunity_id>/substages/<int:substage_id>/remove-from-followup/', 
        BuyingProcessViewSet.as_view({
            'delete': 'remove_substage_from_followup'
        }), 
        name='buying-process-substage-remove-followup'),

    # ✅ CRUD Follow-up : Compléter le follow-up d'un substage
    path('buying-processes/opportunity/<int:opportunity_id>/substages/<int:substage_id>/complete-followup/', 
        BuyingProcessViewSet.as_view({
            'post': 'complete_substage_followup'
        }), 
        name='buying-process-substage-complete-followup'),

    # ✅ CRUD Follow-up : Récupérer le statut follow-up d'un substage
    path('buying-processes/opportunity/<int:opportunity_id>/substages/<int:substage_id>/followup-status/', 
        BuyingProcessViewSet.as_view({
            'get': 'get_substage_followup_status'
        }), 
        name='buying-process-substage-followup-status'),

    # =========================================================================
    # Pipeline Opportunity
    # =========================================================================
    
    path('buying-processes/opportunity/<int:opportunity_id>/pipeline-status/', 
    BuyingProcessViewSet.as_view({
        'get': 'get_pipeline_status'
    }), 
    name='buying-process-pipeline-status'),

    # # =========================================================================
    # # INTÉGRATION FOLLOW-UP - Via SubStageFollowUpService
    # # =========================================================================
    
    # # Campaign Integration (via SubStageFollowUpService)
    # path('<int:opportunity_id>/pipeline/substages/<int:substage_id>/campaigns/', PipelineViewSet.as_view({
    #     'get': 'list_substage_campaigns'
    # }), name='opportunity-pipeline-substage-campaigns'),
    
    # path('<int:opportunity_id>/pipeline/substages/<int:substage_id>/add-to-followup/', PipelineViewSet.as_view({
    #     'post': 'add_substage_to_followup'
    # }), name='opportunity-pipeline-substage-add-followup'),
    
    # path('<int:opportunity_id>/pipeline/substages/<int:substage_id>/remove-from-followup/', PipelineViewSet.as_view({
    #     'delete': 'remove_substage_from_followup'
    # }), name='opportunity-pipeline-substage-remove-followup'),
    
    # path('<int:opportunity_id>/pipeline/substages/<int:substage_id>/complete-followup/', PipelineViewSet.as_view({
    #     'post': 'complete_substage_followup'
    # }), name='opportunity-pipeline-substage-complete-followup'),
    
    # path('<int:opportunity_id>/pipeline/substages/<int:substage_id>/followup-status/', PipelineViewSet.as_view({
    #     'get': 'get_substage_followup_status'
    # }), name='opportunity-pipeline-substage-followup-status'),
    
    # # Pipeline Activities
    # path('<int:opportunity_id>/pipeline/activities/', PipelineViewSet.as_view({
    #     'get': 'pipeline_activities'
    # }), name='opportunity-pipeline-activities'),
]