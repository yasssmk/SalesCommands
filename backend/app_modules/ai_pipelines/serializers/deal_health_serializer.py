# app_modules/ai_pipelines/serializers/deal_health_serializer.py
"""
Input serializer for the deal-health diagnostic endpoint.

Validates the inbound payload for
    POST /module-ai-pipelines/deal-health/run/

Expected payload:
    {
        "decision_cycle_id": "<uuid>"
    }

Post-validation payload (.validated_data):
    * decision_cycle: DecisionCycle instance (tenant-scoped).
    * client_id:      UUID of the tenant.
"""

from rest_framework import serializers

from app_modules.decision_cycles.models import DecisionCycle
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError


class DealHealthRunInputSerializer(
    ClientScopeManager.SerializerMixin,
    serializers.Serializer,
):
    """
    Validates the input for the deal-health diagnostic endpoint.
    See module docstring for the full validation contract.
    """

    decision_cycle_id = serializers.UUIDField(
        required=True,
        write_only=True,
        help_text='UUID of the DecisionCycle to diagnose.',
    )

    def validate(self, attrs):
        """
        Resolve the DecisionCycle (tenant-scoped) and attach it to
        validated_data along with the client_id.
        """
        client_id = self._get_client_id_from_context()
        decision_cycle_id = attrs.pop('decision_cycle_id')

        try:
            decision_cycle = (
                DecisionCycle.objects
                .select_related('account')
                .get(id=decision_cycle_id, client_id=client_id)
            )
        except DecisionCycle.DoesNotExist:
            raise StandardizedValidationError(
                'The specified decision cycle does not exist '
                'or is not accessible.'
            )

        attrs['decision_cycle'] = decision_cycle
        attrs['client_id'] = client_id
        return attrs
