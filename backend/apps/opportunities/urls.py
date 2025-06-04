from django.urls import path
from .views import (
    OpportunityViewSet, OpportunityLineItemViewSet, OpportunityFinancialSummaryViewSet,
    OpportunitySourceViewSet, OpportunityActivityViewSet
)

urlpatterns = [
    # Opportunities
    path('', OpportunityViewSet.as_view(), name='opportunity-list'),  # For GET and POST requests
    path('<int:pk>/', OpportunityViewSet.as_view(), name='opportunity-detail'),  # For PUT and DELETE by ID
    path('<int:pk>/with-financials/', OpportunityViewSet.as_view(), name='opportunity-with-financials'),
    path('<int:pk>/mark-as-won/', OpportunityViewSet.as_view(), name='opportunity-mark-as-won'),
    path('<int:pk>/mark-as-lost/', OpportunityViewSet.as_view(), name='opportunity-mark-as-lost'),
    path('<int:pk>/assign/', OpportunityViewSet.as_view(), name='opportunity-assign'),
    path('<int:pk>/history/', OpportunityViewSet.as_view(), name='opportunity-history'),
    path('convert-lead/', OpportunityViewSet.as_view(), name='opportunity-convert-lead'),
    path('summary/', OpportunityViewSet.as_view(), name='opportunity-summary'),
    
    # Opportunity Line Items (Products)
    path('line-items/', OpportunityLineItemViewSet.as_view(), name='line-item-list'),
    path('line-items/<int:pk>/', OpportunityLineItemViewSet.as_view(), name='line-item-detail'),
    path('line-items/available-products/', OpportunityLineItemViewSet.as_view(), name='line-item-available-products'),
    
    # Financial Summaries
    path('financials/', OpportunityFinancialSummaryViewSet.as_view(), name='financial-summary-list'),
    path('financials/<int:pk>/', OpportunityFinancialSummaryViewSet.as_view(), name='financial-summary-detail'),
    path('financials/forecast/', OpportunityFinancialSummaryViewSet.as_view(), name='financial-summary-forecast'),
    
    # Opportunity Sources
    path('sources/', OpportunitySourceViewSet.as_view(), name='opportunity-source-list'),
    path('sources/<int:pk>/', OpportunitySourceViewSet.as_view(), name='opportunity-source-detail'),
    path('sources/<int:pk>/accept-conversion/', OpportunitySourceViewSet.as_view(), name='opportunity-source-accept'),
    path('sources/<int:pk>/reject-conversion/', OpportunitySourceViewSet.as_view(), name='opportunity-source-reject'),
    
    # Opportunity Activities
    path('activities/', OpportunityActivityViewSet.as_view(), name='opportunity-activity-list'),
    path('activities/<int:pk>/', OpportunityActivityViewSet.as_view(), name='opportunity-activity-detail'),
    path('activities/create-activity/', OpportunityActivityViewSet.as_view(), name='opportunity-activity-create'),
    path('activities/opportunity-timeline/', OpportunityActivityViewSet.as_view(), name='opportunity-activity-timeline'),
]