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
    """Full CRUD serializer. owner / client_id / state are read-only.

    Attainment (``current_value`` / ``progress_ratio``) is computed, not stored:
    it comes from the quotas progress service (sub-step 4/4bis), which already
    resolves the owner's perimeter (individual / manager recursive subtree /
    admin) and window. On a LIST the viewset precomputes the whole page in ONE
    batch pass and hands the result to this serializer via
    ``context['progress_map']`` — so no per-row query. On detail / write it falls
    back to a single, memoised computation.
    """

    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    state = serializers.CharField(read_only=True)
    is_current = serializers.BooleanField(read_only=True)
    current_value = serializers.SerializerMethodField()
    progress_ratio = serializers.SerializerMethodField()

    class Meta:
        model = Quota
        fields = [
            'id', 'owner', 'metric', 'target_value',
            'period_start', 'period_end', 'source_campaign',
            'state', 'is_current',
            'current_value', 'progress_ratio',
            'client_id', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'owner', 'client_id', 'created_at', 'updated_at']

    def _progress(self, obj):
        """The quota's QuotaProgress. Reads the batch map when the viewset
        supplied one (LIST — no per-row query); otherwise computes it once and
        memoises it on the shared context (so the two method fields below don't
        double-compute)."""
        pmap = self.context.get('progress_map')
        if pmap is not None and obj.id in pmap:
            return pmap[obj.id]
        cache = self.context.setdefault('_progress_cache', {})
        if obj.id not in cache:
            from .services.progress import compute_progress
            cache[obj.id] = compute_progress(obj)
        return cache[obj.id]

    def get_current_value(self, obj):
        return self._progress(obj).current_value

    def get_progress_ratio(self, obj):
        # value / target, NOT clamped (over-achievement > 1 stays visible); null
        # when target_value <= 0 (ratio undefined) — see progress._ratio.
        return self._progress(obj).ratio

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
