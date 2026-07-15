# app_modules/bi/serializers.py
"""
Serializers for the BI list surface (currently the /bi/todo/ endpoint).

TodoRowSerializer projects one Activity of the todo population into the columns
the Rep todo table needs, exposing the ids the frontend deep-links on (account,
decision_cycle, campaign). It reuses the activities module's minimal nested
serializers so the shapes stay consistent with the rest of the app.
"""

from rest_framework import serializers

from app_modules.activities.models import Activity
from app_modules.activities.serializers import (
    ActivityAccountSerializer,
    ActivityDecisionCycleSerializer,
    ActivityUserSerializer,
)


class TodoRowSerializer(serializers.ModelSerializer):
    """One todo row. `effective_date` is the COALESCE(due_date, scheduled_date)
    annotation carried by build_todo_population — the same field the windows and
    the sort use, so the row's placement matches the tile it came from.

    `owner` is the responsible person: harmless for the rep list (it's the rep
    themselves / C6 / an accepted invite), and the "who" column for the manager
    team list. Views select_related('owner') so it stays query-bounded."""

    activity_type_display = serializers.CharField(source='get_activity_type_display', read_only=True)
    owner = ActivityUserSerializer(read_only=True)
    account = ActivityAccountSerializer(read_only=True)
    decision_cycle = ActivityDecisionCycleSerializer(read_only=True)
    campaign = serializers.SerializerMethodField(read_only=True)
    effective_date = serializers.DateField(source='_effective_date', read_only=True)

    class Meta:
        model = Activity
        fields = [
            'id', 'title',
            'activity_type', 'activity_type_display',
            'due_date', 'scheduled_date', 'effective_date',
            'owner', 'account', 'decision_cycle', 'campaign',
        ]
        read_only_fields = fields

    def get_campaign(self, obj):
        if obj.campaign_id:
            return {'id': str(obj.campaign_id), 'name': getattr(obj.campaign, 'name', None)}
        return None
