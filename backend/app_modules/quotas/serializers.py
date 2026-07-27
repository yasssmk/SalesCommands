# app_modules/quotas/serializers.py
"""
Serializer for the personal Quota (objective) CRUD.

owner and client_id are set server-side from the request (the creator is the
owner); the derived state is exposed read-only. There is NO overlap validation
— concurrent overlapping objectives are allowed by design.
"""

from rest_framework import serializers

from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages

from .models import Quota


class QuotaSerializer(serializers.ModelSerializer):
    """Full CRUD serializer. owner / client_id / state are read-only."""

    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    state = serializers.CharField(read_only=True)
    is_current = serializers.BooleanField(read_only=True)

    class Meta:
        model = Quota
        fields = [
            'id', 'owner', 'metric', 'target_value',
            'period_start', 'period_end', 'source_campaign',
            'state', 'is_current',
            'client_id', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'owner', 'client_id', 'created_at', 'updated_at']

    def validate(self, attrs):
        """period_end must not precede period_start (both are NOT NULL)."""
        start = attrs.get('period_start', getattr(self.instance, 'period_start', None))
        end = attrs.get('period_end', getattr(self.instance, 'period_end', None))
        if start and end and end < start:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATE_RANGE, field='period_end'
            )
        return attrs

    def create(self, validated_data):
        request = self.context['request']
        client_id = self.context.get('client_id')
        instance = Quota(owner=request.user, **validated_data)
        instance.save(user=request.user, client_id=client_id)
        return instance

    def update(self, instance, validated_data):
        request = self.context['request']
        # owner is immutable — a quota always belongs to its creator.
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save(user=request.user)
        return instance
