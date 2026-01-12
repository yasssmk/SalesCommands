# app_modules/activities/filters.py
"""
FilterSet for Activity module.

Uses BaseInFilter to accept comma-separated values for choice fields.
Example: ?status=PLANNED,IN_PROGRESS → filters for status IN ['PLANNED', 'IN_PROGRESS']
"""

import django_filters
from django_filters import BaseInFilter, CharFilter, UUIDFilter, DateFilter

from .models import Activity


class CharInFilter(BaseInFilter, CharFilter):
    """
    Filter that accepts comma-separated string values.
    Example: ?status=PLANNED,IN_PROGRESS → ['PLANNED', 'IN_PROGRESS']
    """
    pass


class ActivityFilter(django_filters.FilterSet):
    """
    FilterSet for Activity model.
    
    Supports:
    - Multi-value filters (comma-separated): activity_type, status, outcome
    - Single value filters: account, owner, decision_cycle, decision_step
    - Date range filters: scheduled_date, due_date, completed_at
    """
    
    # Multi-value filters (accept comma-separated values)
    activity_type = CharInFilter(field_name='activity_type', lookup_expr='in')
    status = CharInFilter(field_name='status', lookup_expr='in')
    outcome = CharInFilter(field_name='outcome', lookup_expr='in')
    
    # Single value filters (UUID)
    account = UUIDFilter(field_name='account_id')
    owner = UUIDFilter(field_name='owner_id')
    decision_cycle = UUIDFilter(field_name='decision_cycle_id')
    decision_step = UUIDFilter(field_name='decision_step_id')
    
    # Date filters
    scheduled_date = DateFilter(field_name='scheduled_date')
    scheduled_date_from = DateFilter(field_name='scheduled_date', lookup_expr='gte')
    scheduled_date_to = DateFilter(field_name='scheduled_date', lookup_expr='lte')
    
    due_date = DateFilter(field_name='due_date')
    due_date_from = DateFilter(field_name='due_date', lookup_expr='gte')
    due_date_to = DateFilter(field_name='due_date', lookup_expr='lte')
    
    completed_at_from = DateFilter(field_name='completed_at', lookup_expr='gte')
    completed_at_to = DateFilter(field_name='completed_at', lookup_expr='lte')
    
    # Boolean filters
    is_overdue = django_filters.BooleanFilter(method='filter_is_overdue')
    has_decision_step = django_filters.BooleanFilter(method='filter_has_decision_step')
    
    class Meta:
        model = Activity
        fields = [
            'activity_type', 'status', 'outcome',
            'account', 'owner', 'decision_cycle', 'decision_step',
            'scheduled_date', 'scheduled_date_from', 'scheduled_date_to',
            'due_date', 'due_date_from', 'due_date_to',
            'completed_at_from', 'completed_at_to',
            'is_overdue', 'has_decision_step'
        ]
    
    def filter_is_overdue(self, queryset, name, value):
        """
        Filter activities by overdue status.
        
        ?is_overdue=true  → activities past due_date and not completed/cancelled
        ?is_overdue=false → activities not overdue
        """
        from django.utils import timezone
        from .constants import ActivityStatus
        
        today = timezone.now().date()
        
        if value:
            return queryset.filter(
                due_date__lt=today,
                status__in=[ActivityStatus.PLANNED, ActivityStatus.IN_PROGRESS]
            )
        else:
            return queryset.exclude(
                due_date__lt=today,
                status__in=[ActivityStatus.PLANNED, ActivityStatus.IN_PROGRESS]
            )
    
    def filter_has_decision_step(self, queryset, name, value):
        """
        Filter activities by whether they have a decision step.
        
        ?has_decision_step=true  → activities linked to a decision step
        ?has_decision_step=false → activities without a decision step
        """
        if value:
            return queryset.filter(decision_step__isnull=False)
        else:
            return queryset.filter(decision_step__isnull=True)