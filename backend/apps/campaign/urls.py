# apps/campaign/urls.py

from django.urls import path
from apps.campaign.views.campaign_views import CampaignViewSet
from apps.campaign.views.campaign_objective_views import CampaignObjectiveViewSet
from apps.campaign.views.campaign_target_views import CampaignTargetViewSet

# Convert ViewSets to use as_view()
campaign_list = CampaignViewSet.as_view({
    'get': 'list',
    'post': 'create'
})

campaign_detail = CampaignViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})

campaign_summary = CampaignViewSet.as_view({
    'get': 'summary'
})

# CampaignObjective views
objective_list = CampaignObjectiveViewSet.as_view({
    'get': 'list',
    'post': 'create'
})

objective_detail = CampaignObjectiveViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})

objective_update_progress = CampaignObjectiveViewSet.as_view({
    'post': 'update_progress'
})

# CampaignTarget views
target_list = CampaignTargetViewSet.as_view({
    'get': 'list',
    'post': 'create'
})

target_detail = CampaignTargetViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})

target_update_status = CampaignTargetViewSet.as_view({
    'post': 'update_status'
})

target_bulk_create = CampaignTargetViewSet.as_view({
    'post': 'bulk_create'
})

urlpatterns = [
    # Campaign endpoints
    path('campaigns/', campaign_list, name='campaign-list'),
    path('campaigns/<int:pk>/', campaign_detail, name='campaign-detail'),
    path('campaigns/<int:pk>/summary/', campaign_summary, name='campaign-summary'),
    
    # CampaignObjective endpoints
    path('objectives/', objective_list, name='objective-list'),
    path('objectives/<int:pk>/', objective_detail, name='objective-detail'),
    path('objectives/<int:pk>/update-progress/', objective_update_progress, name='objective-update-progress'),
    path('campaigns/<int:campaign_id>/objectives/', objective_list, name='campaign-objectives'),
    
    # CampaignTarget endpoints
    path('targets/', target_list, name='target-list'),
    path('targets/<int:pk>/', target_detail, name='target-detail'),
    path('targets/<int:pk>/update-status/', target_update_status, name='target-update-status'),
    path('targets/bulk-create/', target_bulk_create, name='target-bulk-create'),
    path('campaigns/<int:campaign_id>/targets/', target_list, name='campaign-targets'),
]