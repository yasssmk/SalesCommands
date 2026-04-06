# app_modules/signals/urls.py
"""
URL configuration for the Signals module.

Follows the same patterns as app_modules/activities/urls.py.
Lazy imports to avoid circular imports.

Mount points (defined in root urls.py):
  /app/signals/qualification/   → QualificationSignalViewSet
  /app/signals/tech-stack/      → TechStackSignalViewSet
  /app/signals/choices/         → SignalChoicesView
"""

from django.urls import path

app_name = 'module_signals'


def get_urlpatterns():
    """Lazy imports to avoid circular import."""
    from .views import (
        QualificationSignalViewSet,
        TechStackSignalViewSet,
        SignalChoicesView,
    )

    return [
        # =====================================================================
        # CHOICES — before CRUD to avoid conflict with {pk}
        # =====================================================================
        path('choices/', SignalChoicesView.as_view(), name='choices'),

        # =====================================================================
        # QUALIFICATION SIGNALS
        # =====================================================================
        path('qualification/', QualificationSignalViewSet.as_view({
            'get':  'list',
            'post': 'create',
        }), name='qualification-list'),

        path('qualification/<uuid:pk>/', QualificationSignalViewSet.as_view({
            'get':    'retrieve',
            'patch':  'partial_update',
            'put':    'update',
            'delete': 'destroy',
        }), name='qualification-detail'),

        path('qualification/<uuid:pk>/validate/', QualificationSignalViewSet.as_view({
            'post': 'validate_signal',
        }), name='qualification-validate'),

        path('qualification/<uuid:pk>/reject/', QualificationSignalViewSet.as_view({
            'post': 'reject_signal',
        }), name='qualification-reject'),

        path('qualification/<uuid:pk>/merge/', QualificationSignalViewSet.as_view({
            'post': 'merge_signal',
        }), name='qualification-merge'),

        path('qualification/<uuid:pk>/supersede/', QualificationSignalViewSet.as_view({
            'post': 'supersede_signal',
        }), name='qualification-supersede'),

        # =====================================================================
        # TECH STACK SIGNALS
        # =====================================================================
        path('tech-stack/', TechStackSignalViewSet.as_view({
            'get':  'list',
            'post': 'create',
        }), name='tech-stack-list'),

        path('tech-stack/<uuid:pk>/', TechStackSignalViewSet.as_view({
            'get':    'retrieve',
            'patch':  'partial_update',
            'put':    'update',
            'delete': 'destroy',
        }), name='tech-stack-detail'),

        path('tech-stack/<uuid:pk>/validate/', TechStackSignalViewSet.as_view({
            'post': 'validate_signal',
        }), name='tech-stack-validate'),

        path('tech-stack/<uuid:pk>/reject/', TechStackSignalViewSet.as_view({
            'post': 'reject_signal',
        }), name='tech-stack-reject'),

        path('tech-stack/<uuid:pk>/merge/', TechStackSignalViewSet.as_view({
            'post': 'merge_signal',
        }), name='tech-stack-merge'),

        path('tech-stack/<uuid:pk>/supersede/', TechStackSignalViewSet.as_view({
            'post': 'supersede_signal',
        }), name='tech-stack-supersede'),
    ]


urlpatterns = get_urlpatterns()