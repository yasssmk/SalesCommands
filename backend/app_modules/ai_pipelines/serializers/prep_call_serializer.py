# app_modules/ai_pipelines/serializers/prep_call_serializer.py
"""
Serializers for the prep-call tactical brief endpoints.

PrepCallRunInputSerializer — validates POST /prep-call/run/ payload.
PrepCallSnapshotSerializer — read-only output for GET /prep-call/by-activity/<uuid>/.
"""

from rest_framework import serializers

from app_modules.activities.models import Activity
from core.client_scope import ClientScopeManager
from core.error_messages import AIPipelineErrorMessages
from core.exceptions import StandardizedValidationError

from ..models import PrepCallSnapshot


class _LanguageOverrideSerializer(serializers.Serializer):
    """One language chosen for a recipient of an AI message (G11): its ref
    (the roster label the languages preview returned) and a BCP-47 tag —
    validated by the decision_cycles validator (the profile's own rule)."""

    ref = serializers.CharField(max_length=200)
    language = serializers.CharField(max_length=50)

    def validate_language(self, value):
        from app_modules.decision_cycles.services.stakeholder_service import (
            validate_language_tag,
        )
        return validate_language_tag(value)


class PrepCallRunInputSerializer(
    ClientScopeManager.SerializerMixin,
    serializers.Serializer,
):
    """
    Validates the input for the prep-call brief endpoint.

    Expected payload:
        {
            "activity_id": "<uuid>",
            "language_overrides": [{"ref": "<label>", "language": "fr"}]   # optional, G11
        }

    No `contact_id` (sprint 2 Game Plan, S2 — C2-11 / TD-325, PO decision
    Q8): the people of the brief come from the activity itself, server-side
    (TD-46 / TD-48); a `contact_id` sent is ignored — no FK received.
    PrepCallSnapshot.target_contact stays, to read the v1 snapshots.

    Post-validation (.validated_data):
        * activity:       Activity instance (tenant-scoped).
        * client_id:      UUID of the tenant.
    """

    activity_id = serializers.UUIDField(
        required=True,
        write_only=True,
        help_text='UUID of the Activity to prepare for.',
    )
    # G11: per recipient, the language of its AI message for THIS generation
    # (the recipient is resolved by the roster in the view, never guessed).
    language_overrides = _LanguageOverrideSerializer(many=True, required=False, write_only=True)

    def validate(self, attrs):
        client_id = self._get_client_id_from_context()
        activity_id = attrs.pop('activity_id')

        try:
            activity = (
                Activity.objects
                .select_related('decision_cycle', 'account')
                .get(id=activity_id, client_id=client_id)
            )
        except Activity.DoesNotExist:
            raise StandardizedValidationError(
                AIPipelineErrorMessages.ACTIVITY_NOT_FOUND
            )

        # The activity type, its status and its context are BUSINESS RULES
        # (G3): answered by the view with 200 + an INFO code
        # (services/game_plan_access.py game_plan_blocked_reason), never a 400.

        attrs['activity'] = activity
        attrs['client_id'] = client_id
        return attrs


class PrepCallSnapshotSerializer(
    ClientScopeManager.SerializerMixin,
    serializers.ModelSerializer,
):
    """
    Read-only serializer for PrepCallSnapshot (GET by-activity).
    """

    pipeline_run_summary = serializers.SerializerMethodField()

    class Meta:
        model = PrepCallSnapshot
        fields = [
            'id',
            'activity',
            'target_contact',
            'brief_mode',
            'schema_version',
            'output_kind',
            'deal_health_snapshot',
            'deal_health_schema_version',
            'brief',
            'input_hash',
            'snapshot_date',
            'pipeline_run',
            'pipeline_run_summary',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_pipeline_run_summary(self, obj):
        run = obj.pipeline_run
        if not run:
            return None
        return {
            'run_id': str(run.id),
            'status': run.status,
            'total_tokens_used': run.total_tokens_used,
            'total_duration_ms': run.total_duration_ms,
            'created_at': (
                run.created_at.isoformat() if run.created_at else None
            ),
        }
