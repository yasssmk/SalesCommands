# app_modules/signals/urls.py
"""
URL configuration for the Signals module.

Lazy imports to avoid circular imports at startup.

Mount point (defined in root urls.py):
  /module-signals/ → app_modules/signals/urls.py

All paths below are relative to that mount point.
"""

from django.urls import path

app_name = 'module_signals'


def get_urlpatterns():
    """Lazy imports to avoid circular import at Django startup."""
    from .views import (
        PeopleSignalViewSet,
        PainSignalViewSet,
        ObjectiveSignalViewSet,
        TechStackSignalViewSet,
        SignalChoicesView,
    )

    return [

        # =====================================================================
        # CHOICES — before CRUD to avoid conflict with {pk}
        # =====================================================================

        path(
            'choices/',
            SignalChoicesView.as_view(),
            name='choices',
        ),

        # =====================================================================
        # PEOPLE SIGNALS
        # =====================================================================

        path(
            'people/',
            PeopleSignalViewSet.as_view({'get': 'list', 'post': 'create'}),
            name='people-list',
        ),
        path(
            'people/<uuid:pk>/',
            PeopleSignalViewSet.as_view({
                'get':    'retrieve',
                'patch':  'partial_update',
                'put':    'update',
                'delete': 'destroy',
            }),
            name='people-detail',
        ),
        path(
            'people/<uuid:pk>/validate/',
            PeopleSignalViewSet.as_view({'post': 'validate_signal'}),
            name='people-validate',
        ),
        path(
            'people/<uuid:pk>/reject/',
            PeopleSignalViewSet.as_view({'post': 'reject_signal'}),
            name='people-reject',
        ),

        # =====================================================================
        # PAIN SIGNALS
        # =====================================================================

        path(
            'pain/',
            PainSignalViewSet.as_view({'get': 'list', 'post': 'create'}),
            name='pain-list',
        ),
        path(
            'pain/<uuid:pk>/',
            PainSignalViewSet.as_view({
                'get':    'retrieve',
                'patch':  'partial_update',
                'put':    'update',
                'delete': 'destroy',
            }),
            name='pain-detail',
        ),
        path(
            'pain/<uuid:pk>/validate/',
            PainSignalViewSet.as_view({'post': 'validate_signal'}),
            name='pain-validate',
        ),
        path(
            'pain/<uuid:pk>/reject/',
            PainSignalViewSet.as_view({'post': 'reject_signal'}),
            name='pain-reject',
        ),

        # =====================================================================
        # OBJECTIVE SIGNALS
        # =====================================================================

        path(
            'objective/',
            ObjectiveSignalViewSet.as_view({'get': 'list', 'post': 'create'}),
            name='objective-list',
        ),
        path(
            'objective/<uuid:pk>/',
            ObjectiveSignalViewSet.as_view({
                'get':    'retrieve',
                'patch':  'partial_update',
                'put':    'update',
                'delete': 'destroy',
            }),
            name='objective-detail',
        ),
        path(
            'objective/<uuid:pk>/validate/',
            ObjectiveSignalViewSet.as_view({'post': 'validate_signal'}),
            name='objective-validate',
        ),
        path(
            'objective/<uuid:pk>/reject/',
            ObjectiveSignalViewSet.as_view({'post': 'reject_signal'}),
            name='objective-reject',
        ),

        # =====================================================================
        # TECH STACK SIGNALS
        # =====================================================================

        path(
            'tech-stack/',
            TechStackSignalViewSet.as_view({'get': 'list', 'post': 'create'}),
            name='tech-stack-list',
        ),
        path(
            'tech-stack/<uuid:pk>/',
            TechStackSignalViewSet.as_view({
                'get':    'retrieve',
                'patch':  'partial_update',
                'put':    'update',
                'delete': 'destroy',
            }),
            name='tech-stack-detail',
        ),
        path(
            'tech-stack/<uuid:pk>/validate/',
            TechStackSignalViewSet.as_view({'post': 'validate_signal'}),
            name='tech-stack-validate',
        ),
        path(
            'tech-stack/<uuid:pk>/reject/',
            TechStackSignalViewSet.as_view({'post': 'reject_signal'}),
            name='tech-stack-reject',
        ),
    ]


urlpatterns = get_urlpatterns()