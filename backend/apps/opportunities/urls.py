# apps/opportunities/urls.py

from django.urls import path
from .views.opportunity_views import OpportunityViewSet
from .views.opportunity_financial_views import OpportunityLineItemViewSet, OpportunityFinancialSummaryViewSet
from .views.opportunity_tracking_views import OpportunitySourceViewSet, OpportunityActivityViewSet

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
]