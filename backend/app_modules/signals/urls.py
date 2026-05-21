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
        PainSignalViewSet,
        ObjectiveSignalViewSet,
        ImpactSignalViewSet,
        PainImpactViewSet,
        TechStackSignalViewSet,
        SignalChoicesView,
        SignalClusterListView,
        SignalClusterDetailView,
        SignalClusterArchiveView,
        SignalClusterUnarchiveView,
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
        # IMPACT SIGNALS
        # =====================================================================

        path(
            'impact/',
            ImpactSignalViewSet.as_view({'get': 'list', 'post': 'create'}),
            name='impact-list',
        ),
        path(
            'impact/<uuid:pk>/',
            ImpactSignalViewSet.as_view({
                'get':    'retrieve',
                'patch':  'partial_update',
                'put':    'update',
                'delete': 'destroy',
            }),
            name='impact-detail',
        ),
        path(
            'impact/<uuid:pk>/validate/',
            ImpactSignalViewSet.as_view({'post': 'validate_signal'}),
            name='impact-validate',
        ),
        path(
            'impact/<uuid:pk>/reject/',
            ImpactSignalViewSet.as_view({'post': 'reject_signal'}),
            name='impact-reject',
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

        # =====================================================================
        # PAIN IMPACTS — no lifecycle, no validate/reject
        # =====================================================================

        path(
            'pain-impacts/',
            PainImpactViewSet.as_view({'get': 'list', 'post': 'create'}),
            name='pain-impact-list',
        ),
        path(
            'pain-impacts/<uuid:pk>/',
            PainImpactViewSet.as_view({
                'get':    'retrieve',
                'patch':  'partial_update',
                'put':    'update',
                'delete': 'destroy',
            }),
            name='pain-impact-detail',
        ),

        # =====================================================================
        # SIGNAL CLUSTERS
        #
        # Order matters here: the literal paths 'clusters/archive/' and
        # 'clusters/unarchive/' MUST appear before the <path:canonical_key>
        # wildcard. Django resolves patterns top-to-bottom and a wildcard
        # would otherwise swallow the literal routes.
        #
        # canonical_key uses <path:> (not <str:>) because the identifier
        # contains colons, e.g. 'pain:OPS:TIME'. Django's default 'str'
        # converter rejects colons; 'path' accepts them along with any
        # printable non-slash character.
        # =====================================================================

        path(
            'clusters/',
            SignalClusterListView.as_view(),
            name='cluster-list',
        ),
        path(
            'clusters/archive/',
            SignalClusterArchiveView.as_view(),
            name='cluster-archive',
        ),
        path(
            'clusters/unarchive/',
            SignalClusterUnarchiveView.as_view(),
            name='cluster-unarchive',
        ),
        path(
            'clusters/<path:canonical_key>/',
            SignalClusterDetailView.as_view(),
            name='cluster-detail',
        ),

    ]


urlpatterns = get_urlpatterns()