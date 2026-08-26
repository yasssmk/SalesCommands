# app_modules/signals/views/signal_counts_view.py
"""
GET /module-signals/by-activity/<uuid:activity_id>/counts/

Returns aggregated signal counts (PENDING / VALIDATED / REJECTED)
for a given activity, broken down by signal type. Used by the
ActivityHeader pending counter badge (Sprint F4).

Response (200):
    {
        "pending":   8,
        "validated": 3,
        "rejected":  1,
        "by_type": {
            "pain":       { "pending": 2, "validated": 1, "rejected": 0 },
            "objective":  { "pending": 1, "validated": 0, "rejected": 0 },
            "impact":     { "pending": 0, "validated": 1, "rejected": 0 },
            "tech_stack": { "pending": 1, "validated": 0, "rejected": 1 },
            "blocker":    { "pending": 1, "validated": 1, "rejected": 0 },
            "next_step":  { "pending": 3, "validated": 0, "rejected": 0 }
        }
    }

Response (404): Activity not found or not owned by tenant.
"""

from django.db.models import Count, Q

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.apps_shared_methods import BaseAPIView
from core.jwt_helpers import CustomJWTAuthentication
from permissions.mixins import ScopedPermission

from app_modules.activities.models import Activity
from app_modules.signals.constants import SignalStatus
from app_modules.signals.models import (
    PainSignal,
    ObjectiveSignal,
    ImpactSignal,
    TechStackSignal,
    BlockerSignal,
    NextStepSignal,
)


SIGNAL_MODELS = {
    'pain': PainSignal,
    'objective': ObjectiveSignal,
    'impact': ImpactSignal,
    'tech_stack': TechStackSignal,
    'blocker': BlockerSignal,
    'next_step': NextStepSignal,
}

STATUS_ANNOTATIONS = {
    'pending': Count('id', filter=Q(status=SignalStatus.PENDING)),
    'validated': Count('id', filter=Q(status=SignalStatus.VALIDATED)),
    'rejected': Count('id', filter=Q(status=SignalStatus.REJECTED)),
}


class SignalCountsByActivityView(BaseAPIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'signals'

    def get(self, request, activity_id):
        client_id = self.get_client_id()

        try:
            activity = Activity.objects.get(id=activity_id, client_id=client_id)
        except Activity.DoesNotExist:
            return Response(
                {'error': 'Activity not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        totals = {'pending': 0, 'validated': 0, 'rejected': 0}
        by_type = {}

        for type_key, model_cls in SIGNAL_MODELS.items():
            row = (
                model_cls.objects
                .filter(client_id=client_id, source_activity=activity)
                # Exclude out-of-taxonomy-domain signals (COST-bug guard) so a
                # flagged, hidden signal never inflates the pending badge.
                .filter(is_domain_valid=True)
                .aggregate(**STATUS_ANNOTATIONS)
            )
            counts = {
                'pending': row['pending'] or 0,
                'validated': row['validated'] or 0,
                'rejected': row['rejected'] or 0,
            }
            by_type[type_key] = counts
            totals['pending'] += counts['pending']
            totals['validated'] += counts['validated']
            totals['rejected'] += counts['rejected']

        return Response({
            **totals,
            'by_type': by_type,
        })
