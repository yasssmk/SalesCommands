# app_modules/ai_pipelines/serializers/transcript_signals_serializer.py
"""
Input serializer for the TranscriptSignals extraction endpoint.

Validates the inbound payload for
    POST /module-ai-pipelines/transcript-signals/extract/

Expected payload
----------------
    {
        "activity_id": "<uuid>",
        "transcript":  "<raw text>"
    }

Validation contract
-------------------
    1. activity_id must parse as a valid UUID (DRF UUIDField).
    2. The referenced Activity must exist AND be scoped to the
       requesting tenant (client_id derived from JWT context).
       Cross-tenant lookups surface as ACTIVITY_NOT_FOUND -- the same
       error as a non-existent activity, to avoid information leakage
       about other tenants' data.
    3. The transcript, after stripping outer whitespace, must be
       between MIN_TRANSCRIPT_LENGTH and MAX_TRANSCRIPT_LENGTH chars
       (declared in app_modules.ai_pipelines.config).

Post-validation payload
-----------------------
After .is_valid(), .validated_data carries:

    * activity:   Activity instance, prefetched with .account,
                  .contacts, .contacts__standard_department to
                  satisfy build_context_layer()'s expected prefetching
                  (avoids N+1 inside the pipeline).
    * transcript: trimmed transcript string.
    * client_id:  UUID of the tenant.

Out of scope
------------
This serializer DOES NOT persist the transcript on the Activity row.
Saving the transcript on Activity.transcript (when the rep wants to
keep it on the CRM record) is a separate `activities/update` call
issued by the frontend. The extraction endpoint only consumes the
transcript for one pipeline run -- the raw text is never stored;
only its sha256 hash is logged on AIPipelineRun (see _create_run).
"""

from rest_framework import serializers

from app_modules.activities.models import Activity
from core.client_scope import ClientScopeManager
from core.error_messages import AIPipelineErrorMessages
from core.exceptions import StandardizedValidationError

from ..config import MAX_TRANSCRIPT_LENGTH, MIN_TRANSCRIPT_LENGTH


class TranscriptSignalsExtractInputSerializer(
    ClientScopeManager.SerializerMixin,
    serializers.Serializer,
):
    """
    Validates the input for the transcript signals extraction endpoint.
    See module docstring for the full validation contract.
    """

    activity_id = serializers.UUIDField(
        required=True,
        write_only=True,
        help_text='UUID of the source Activity (the conversation whose '
                  'transcript is being analysed).',
    )

    transcript = serializers.CharField(
        required=True,
        allow_blank=False,
        # We strip ourselves in validate_transcript() so we can measure
        # the post-strip length against the configured bounds. The DRF
        # built-in trim is too eager and would silently mask blank-only
        # inputs as None.
        trim_whitespace=False,
        help_text=(
            f'Raw transcript text. Length after trimming must be between '
            f'{MIN_TRANSCRIPT_LENGTH} and {MAX_TRANSCRIPT_LENGTH} characters.'
        ),
    )

    run_qualification = serializers.BooleanField(
        required=False,
        default=True,
        help_text='Run qualification signals pipeline (Pain/Objective/Impact/TechStack/Blocker).',
    )

    run_next_steps = serializers.BooleanField(
        required=False,
        default=True,
        help_text='Run next-step suggestions pipeline.',
    )

    # =========================================================================
    # FIELD-LEVEL VALIDATION
    # =========================================================================

    def validate_transcript(self, value):
        """
        Trim outer whitespace and enforce length bounds from config.

        Raises:
            StandardizedValidationError -- TRANSCRIPT_TOO_SHORT / _TOO_LONG.
        """
        trimmed = (value or '').strip()
        if len(trimmed) < MIN_TRANSCRIPT_LENGTH:
            raise StandardizedValidationError(
                AIPipelineErrorMessages.TRANSCRIPT_TOO_SHORT
            )
        if len(trimmed) > MAX_TRANSCRIPT_LENGTH:
            raise StandardizedValidationError(
                AIPipelineErrorMessages.TRANSCRIPT_TOO_LONG
            )
        return trimmed

    # =========================================================================
    # OBJECT-LEVEL VALIDATION
    # =========================================================================

    def validate(self, attrs):
        """
        Resolve the Activity (tenant-scoped, prefetched) and attach it
        to validated_data along with the client_id.

        The Activity queryset uses select_related / prefetch_related
        to match the access pattern of build_context_layer() in
        context.py -- saving N+1 inside the pipeline's session block.

        Raises:
            StandardizedValidationError -- ACTIVITY_NOT_FOUND when the
                activity does not exist OR does not belong to the
                requesting tenant. The error is identical in both
                cases to avoid leaking the existence of cross-tenant
                rows.
            StandardizedValidationError -- NO_PIPELINE_SELECTED when
                both run_qualification and run_next_steps are False.
        """
        if not attrs.get('run_qualification') and not attrs.get('run_next_steps'):
            raise StandardizedValidationError(
                AIPipelineErrorMessages.NO_PIPELINE_SELECTED
            )

        client_id = self._get_client_id_from_context()
        activity_id = attrs.pop('activity_id')

        try:
            # select_related expanded to cover the FK reads performed by
            # SignalSourceSerializer at response-serialisation time.
            # The detail serializer reads source_activity.decision_cycle,
            # .campaign, and .decision_step for the standardised
            # `source_context` block -- prefetching them here keeps the
            # pipeline's response path free of N+1.
            activity = (
                Activity.objects
                .select_related(
                    'account',
                    'decision_cycle',
                    'campaign',
                    'decision_step',
                )
                .prefetch_related('contacts', 'contacts__standard_department')
                .get(id=activity_id, client_id=client_id)
            )
        except Activity.DoesNotExist:
            raise StandardizedValidationError(
                AIPipelineErrorMessages.ACTIVITY_NOT_FOUND
            )

        attrs['activity'] = activity
        attrs['client_id'] = client_id
        return attrs