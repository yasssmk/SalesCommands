# app_modules/campaigns/urls.py
"""
URL configuration for Campaign module.

Follows the same patterns as Activity and Territory URLs.
Lazy imports to avoid circular imports.
"""

from django.urls import path

app_name = 'module_campaigns'


def get_urlpatterns():
    """Lazy imports to avoid circular import."""
    from .views import (
        CampaignViewSet,
        CampaignAccountViewSet,
        CampaignMemberViewSet,
        CampaignObjectiveViewSet,
    )

    return [
        # =================================================================
        # CAMPAIGN — LIST ACTIONS (before CRUD to avoid {id} conflict)
        # =================================================================
        path('my-campaigns/', CampaignViewSet.as_view({
            'get': 'my_campaigns'
        }), name='my-campaigns'),

        # =================================================================
        # CAMPAIGN — CRUD
        # =================================================================
        path('', CampaignViewSet.as_view({
            'get': 'list',
            'post': 'create'
        }), name='list'),

        path('<uuid:pk>/', CampaignViewSet.as_view({
            'get': 'retrieve',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy'
        }), name='detail'),

        # =================================================================
        # CAMPAIGN — LIFECYCLE ACTIONS
        # =================================================================
        path('<uuid:pk>/start/', CampaignViewSet.as_view({
            'post': 'start'
        }), name='start'),

        path('<uuid:pk>/pause/', CampaignViewSet.as_view({
            'post': 'pause'
        }), name='pause'),

        path('<uuid:pk>/resume/', CampaignViewSet.as_view({
            'post': 'resume'
        }), name='resume'),

        path('<uuid:pk>/complete/', CampaignViewSet.as_view({
            'post': 'complete'
        }), name='complete'),

        path('<uuid:pk>/cancel/', CampaignViewSet.as_view({
            'post': 'cancel'
        }), name='cancel'),

        # =================================================================
        # CAMPAIGN — ANALYTICS & EXECUTION ACTIONS
        # =================================================================
        path('<uuid:pk>/dashboard/', CampaignViewSet.as_view({
            'get': 'dashboard'
        }), name='dashboard'),

        path('<uuid:pk>/summary/', CampaignViewSet.as_view({
            'get': 'summary'
        }), name='summary'),

        path('<uuid:pk>/playlist/', CampaignViewSet.as_view({
            'get': 'playlist'
        }), name='playlist'),

        path('<uuid:pk>/generate-activities/', CampaignViewSet.as_view({
            'post': 'generate_activities'
        }), name='generate-activities'),

        # =================================================================
        # CAMPAIGN ACCOUNTS — LIST ACTIONS
        # =================================================================
        path('accounts/by-campaign/', CampaignAccountViewSet.as_view({
            'get': 'by_campaign'
        }), name='accounts-by-campaign'),

        path('accounts/bulk-add/', CampaignAccountViewSet.as_view({
            'post': 'bulk_add'
        }), name='accounts-bulk-add'),

        path('accounts/bulk-remove/', CampaignAccountViewSet.as_view({
            'post': 'bulk_remove'
        }), name='accounts-bulk-remove'),

        # =================================================================
        # CAMPAIGN ACCOUNTS — CRUD
        # =================================================================
        path('accounts/', CampaignAccountViewSet.as_view({
            'get': 'list',
            'post': 'create'
        }), name='accounts-list'),

        path('accounts/<uuid:pk>/', CampaignAccountViewSet.as_view({
            'get': 'retrieve',
            'patch': 'partial_update',
            'delete': 'destroy'
        }), name='accounts-detail'),

        # =================================================================
        # CAMPAIGN ACCOUNTS — STATUS ACTIONS
        # =================================================================
        path('accounts/<uuid:pk>/start-progress/', CampaignAccountViewSet.as_view({
            'post': 'start_progress'
        }), name='accounts-start-progress'),

        path('accounts/<uuid:pk>/request-callback/', CampaignAccountViewSet.as_view({
            'post': 'request_callback'
        }), name='accounts-request-callback'),

        path('accounts/<uuid:pk>/resume-callback/', CampaignAccountViewSet.as_view({
            'post': 'resume_callback'
        }), name='accounts-resume-callback'),

        path('accounts/<uuid:pk>/mark-completed/', CampaignAccountViewSet.as_view({
            'post': 'mark_completed'
        }), name='accounts-mark-completed'),

        path('accounts/<uuid:pk>/mark-stopped/', CampaignAccountViewSet.as_view({
            'post': 'mark_stopped'
        }), name='accounts-mark-stopped'),

        # =================================================================
        # CAMPAIGN MEMBERS — LIST ACTIONS
        # =================================================================
        path('members/by-campaign/', CampaignMemberViewSet.as_view({
            'get': 'by_campaign'
        }), name='members-by-campaign'),

        # =================================================================
        # CAMPAIGN MEMBERS — CRUD
        # =================================================================
        path('members/', CampaignMemberViewSet.as_view({
            'get': 'list',
            'post': 'create'
        }), name='members-list'),

        path('members/<uuid:pk>/', CampaignMemberViewSet.as_view({
            'get': 'retrieve',
            'patch': 'partial_update',
            'delete': 'destroy'
        }), name='members-detail'),

        # =================================================================
        # CAMPAIGN OBJECTIVES — LIST ACTIONS
        # =================================================================
        path('objectives/by-campaign/', CampaignObjectiveViewSet.as_view({
            'get': 'by_campaign'
        }), name='objectives-by-campaign'),

        path('objectives/choices/', CampaignObjectiveViewSet.as_view({
            'get': 'choices'
        }), name='objectives-choices'),

        # =================================================================
        # CAMPAIGN OBJECTIVES — CRUD
        # =================================================================
        path('objectives/', CampaignObjectiveViewSet.as_view({
            'get': 'list',
            'post': 'create'
        }), name='objectives-list'),

        path('objectives/<uuid:pk>/', CampaignObjectiveViewSet.as_view({
            'get': 'retrieve',
            'patch': 'partial_update',
            'delete': 'destroy'
        }), name='objectives-detail'),
    ]


urlpatterns = get_urlpatterns()