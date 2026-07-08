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
        TechStackSignalViewSet,
        BlockerSignalViewSet,
        NextStepSignalViewSet,
        PeopleSignalViewSet,
        ConstraintSignalViewSet,
        SignalChoicesView,
        SignalClusterListView,
        SignalClusterDetailView,
        SignalClusterArchiveView,
        SignalClusterUnarchiveView,
        SignalCountsByActivityView,
    )

    return [

        # =====================================================================
        # COUNTS — aggregated signal counts by activity
        # =====================================================================

        path(
            'by-activity/<uuid:activity_id>/counts/',
            SignalCountsByActivityView.as_view(),
            name='signal-counts-by-activity',
        ),

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
        path(
            'pain/<uuid:pk>/reopen/',
            PainSignalViewSet.as_view({'post': 'reopen_signal'}),
            name='pain-reopen',
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
        path(
            'objective/<uuid:pk>/reopen/',
            ObjectiveSignalViewSet.as_view({'post': 'reopen_signal'}),
            name='objective-reopen',
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
        path(
            'impact/<uuid:pk>/reopen/',
            ImpactSignalViewSet.as_view({'post': 'reopen_signal'}),
            name='impact-reopen',
        ),

        # =====================================================================
        # TECH STACK SIGNALS
        # =====================================================================

        path(
            'tech-stack/',
            TechStackSignalViewSet.as_view({'get': 'list', 'post': 'create'}),
            name='tech-stack-list',
        ),
        # Literal 'detected/' must precede the <uuid:pk> route so it is
        # not captured as a detail lookup.
        path(
            'tech-stack/detected/',
            TechStackSignalViewSet.as_view({'get': 'detected'}),
            name='tech-stack-detected',
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
        path(
            'tech-stack/<uuid:pk>/reopen/',
            TechStackSignalViewSet.as_view({'post': 'reopen_signal'}),
            name='tech-stack-reopen',
        ),

        # =====================================================================
        # BLOCKER SIGNALS
        # =====================================================================

        path(
            'blockers/',
            BlockerSignalViewSet.as_view({'get': 'list', 'post': 'create'}),
            name='blocker-list',
        ),
        path(
            'blockers/<uuid:pk>/',
            BlockerSignalViewSet.as_view({
                'get':    'retrieve',
                'patch':  'partial_update',
                'put':    'update',
                'delete': 'destroy',
            }),
            name='blocker-detail',
        ),
        path(
            'blockers/<uuid:pk>/validate/',
            BlockerSignalViewSet.as_view({'post': 'validate_signal'}),
            name='blocker-validate',
        ),
        path(
            'blockers/<uuid:pk>/reject/',
            BlockerSignalViewSet.as_view({'post': 'reject_signal'}),
            name='blocker-reject',
        ),
        path(
            'blockers/<uuid:pk>/reopen/',
            BlockerSignalViewSet.as_view({'post': 'reopen_signal'}),
            name='blocker-reopen',
        ),

        # =====================================================================
        # NEXT STEP SIGNALS
        # =====================================================================

        path(
            'next-steps/',
            NextStepSignalViewSet.as_view({'get': 'list', 'post': 'create'}),
            name='next-step-list',
        ),
        path(
            'next-steps/<uuid:pk>/',
            NextStepSignalViewSet.as_view({
                'get':    'retrieve',
                'patch':  'partial_update',
                'put':    'update',
                'delete': 'destroy',
            }),
            name='next-step-detail',
        ),
        path(
            'next-steps/<uuid:pk>/validate/',
            NextStepSignalViewSet.as_view({'post': 'validate_signal'}),
            name='next-step-validate',
        ),
        path(
            'next-steps/<uuid:pk>/reject/',
            NextStepSignalViewSet.as_view({'post': 'reject_signal'}),
            name='next-step-reject',
        ),
        path(
            'next-steps/<uuid:pk>/reopen/',
            NextStepSignalViewSet.as_view({'post': 'reopen_signal'}),
            name='next-step-reopen',
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
        path(
            'people/<uuid:pk>/reopen/',
            PeopleSignalViewSet.as_view({'post': 'reopen_signal'}),
            name='people-reopen',
        ),

        # =====================================================================
        # CONSTRAINT SIGNALS
        # =====================================================================

        path(
            'constraints/',
            ConstraintSignalViewSet.as_view({'get': 'list', 'post': 'create'}),
            name='constraint-list',
        ),
        path(
            'constraints/<uuid:pk>/',
            ConstraintSignalViewSet.as_view({
                'get':    'retrieve',
                'patch':  'partial_update',
                'put':    'update',
                'delete': 'destroy',
            }),
            name='constraint-detail',
        ),
        path(
            'constraints/<uuid:pk>/validate/',
            ConstraintSignalViewSet.as_view({'post': 'validate_signal'}),
            name='constraint-validate',
        ),
        path(
            'constraints/<uuid:pk>/reject/',
            ConstraintSignalViewSet.as_view({'post': 'reject_signal'}),
            name='constraint-reject',
        ),
        path(
            'constraints/<uuid:pk>/reopen/',
            ConstraintSignalViewSet.as_view({'post': 'reopen_signal'}),
            name='constraint-reopen',
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