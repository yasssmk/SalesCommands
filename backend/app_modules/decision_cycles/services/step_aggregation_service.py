# app_modules/decision_cycles/services/step_aggregation_service.py
"""
Step Aggregation Service.

Aggregates data from Activities into DecisionStep computed fields.
Single source of truth for:
- Stakeholders (contacts from activities + manual contacts)
- Departments (from activity contacts + manual departments)
- Timeline (effective start/end dates from activities)

Replaces business logic previously in DecisionStep model @property methods.
Model properties now delegate to this service for backward compatibility.

Usage:
    service = StepAggregationService()

    # Single step (detail view — triggers DB queries)
    contacts = service.get_aggregated_contacts(step)
    timeline = service.get_timeline(step)

    # Bulk (list/timeline view — zero DB queries, uses prefetched data)
    bulk = service.get_bulk_aggregation(steps_queryset)
"""

from core.logging import get_logger

logger = get_logger(__name__)


class StepAggregationService:
    """
    Aggregates Activity data into DecisionStep-level insights.

    Design:
    - Stateless: no stored state between calls.
    - Single-instance methods: trigger DB queries, suitable for detail views.
    - Bulk methods: operate on prefetched data only, zero additional queries.
    - Returns plain dicts/lists (serializable), not model instances.
    """

    # ------------------------------------------------------------------
    # SINGLE-INSTANCE METHODS (detail view — DB queries acceptable)
    # ------------------------------------------------------------------

    def get_aggregated_contacts(self, step):
        """
        Contacts from linked activities only (excludes manual step contacts).

        Returns list of dicts with contact info + department name.
        Triggers 1 DB query.
        """
        from app_modules.contacts.models import Contact

        contacts = Contact.objects.filter(
            activities__decision_step=step
        ).select_related('standard_department').distinct()

        return [
            {
                'id': str(c.id),
                'first_name': c.first_name,
                'last_name': c.last_name,
                'email': c.email,
                'job_title': c.job_title,
                'department_name': (
                    c.standard_department.get_name_display()
                    if c.standard_department else None
                ),
            }
            for c in contacts
        ]

    def get_aggregated_departments(self, step):
        """
        Departments from activity contacts' standard_department.

        Returns list of dicts {id, name}. Triggers 1 DB query.
        """
        from app_modules.core_modules.models import StandardDepartment

        departments = StandardDepartment.objects.filter(
            module_contacts__activities__decision_step=step
        ).distinct()

        return [
            {'id': str(d.id), 'name': d.get_name_display()}
            for d in departments
        ]

    def get_all_contacts(self, step):
        """
        Merged: manual step contacts + activity contacts, deduplicated.
        Each entry includes a 'source' field: 'manual', 'activity', or 'both'.

        Returns list of dicts. Triggers ~3 DB queries.
        """
        from app_modules.contacts.models import Contact

        # Collect IDs from both sources
        manual_ids = set(
            step.step_contacts.values_list('contact_id', flat=True)
        )
        activity_ids = set(
            Contact.objects.filter(
                activities__decision_step=step
            ).values_list('id', flat=True)
        )

        all_ids = manual_ids | activity_ids
        if not all_ids:
            return []

        contacts = Contact.objects.filter(
            id__in=all_ids
        ).select_related('standard_department')

        return [
            {
                'id': str(c.id),
                'first_name': c.first_name,
                'last_name': c.last_name,
                'email': c.email,
                'job_title': c.job_title,
                'department_name': (
                    c.standard_department.get_name_display()
                    if c.standard_department else None
                ),
                'source': self._resolve_source(c.id, manual_ids, activity_ids),
            }
            for c in contacts
        ]

    def get_all_departments(self, step):
        """
        Merged: manual step departments + activity contact departments, deduplicated.

        Returns list of dicts {id, name}. Triggers ~2 DB queries.
        """
        from app_modules.core_modules.models import StandardDepartment

        manual_dept_ids = set(
            step.step_departments.values_list('department_id', flat=True)
        )
        activity_dept_ids = set(
            StandardDepartment.objects.filter(
                module_contacts__activities__decision_step=step
            ).values_list('id', flat=True)
        )

        all_ids = manual_dept_ids | activity_dept_ids
        if not all_ids:
            return []

        departments = StandardDepartment.objects.filter(id__in=all_ids)

        return [
            {'id': str(d.id), 'name': d.get_name_display()}
            for d in departments
        ]

    def get_effective_start_date(self, step):
        """
        Date of first completed activity linked to this step.
        Fallback: first activity by scheduled_date.

        Returns date or None. Triggers 1-2 DB queries.
        """
        from app_modules.activities.constants import ActivityStatus

        first_completed = step.activities.filter(
            status=ActivityStatus.COMPLETED
        ).order_by('completed_at').first()

        if first_completed:
            if first_completed.completed_at:
                return first_completed.completed_at.date()
            return first_completed.scheduled_date

        # Fallback: first scheduled activity
        first_activity = step.activities.exclude(
            scheduled_date__isnull=True
        ).order_by('scheduled_date').first()

        if first_activity:
            return first_activity.scheduled_date

        return None

    def get_effective_end_date(self, step):
        """
        Expected end derived from activities:
        - Priority 1: Last planned activity's due_date or scheduled_date
        - Priority 2: Last completed activity's completed_at

        Returns date or None. Triggers 1-2 DB queries.
        """
        from app_modules.activities.constants import ActivityStatus
        from django.db.models.functions import Coalesce

        # Priority 1: last planned activity date
        last_planned = step.activities.filter(
            status=ActivityStatus.PLANNED
        ).exclude(
            scheduled_date__isnull=True, due_date__isnull=True
        ).order_by(
            Coalesce('due_date', 'scheduled_date').desc()
        ).first()

        if last_planned:
            return last_planned.due_date or last_planned.scheduled_date

        # Priority 2: last completed activity date
        last_completed = step.activities.filter(
            status=ActivityStatus.COMPLETED,
            completed_at__isnull=False
        ).order_by('-completed_at').first()

        if last_completed:
            return last_completed.completed_at.date()

        return None

    def get_timeline(self, step):
        """
        Full timeline dict for a single step.

        Returns dict with effective dates, manual expected_end, and overdue flag.
        """
        from django.utils import timezone

        effective_start = self.get_effective_start_date(step)
        effective_end = self.get_effective_end_date(step)
        expected_end = step.expected_end
        today = timezone.now().date()

        is_overdue = False
        if expected_end and expected_end < today:
            is_overdue = True

        return {
            'effective_start': effective_start,
            'effective_end': effective_end,
            'manual_expected_end': expected_end,
            'is_overdue': is_overdue,
        }

    # ------------------------------------------------------------------
    # BULK METHOD (list/timeline view — zero DB queries)
    # ------------------------------------------------------------------

    def get_bulk_aggregation(self, steps):
        """
        Bulk aggregation for list/timeline views.

        Operates entirely on prefetched data:
        - step._prefetched_step_contacts  (to_attr from Prefetch)
        - step._prefetched_step_departments  (to_attr from Prefetch)
        - step activities from prefetch cache (with contacts prefetched)

        Returns dict keyed by step.id:
        {
            step_id: {
                'all_contacts_count': int,
                'all_departments_list': [{'id': ..., 'name': ...}],
                'effective_start_date': date | None,
                'effective_end_date': date | None,
            }
        }
        """
        results = {}

        for step in steps:
            activities = self._get_prefetched_activities(step)
            manual_contacts = getattr(step, '_prefetched_step_contacts', [])
            manual_departments = getattr(step, '_prefetched_step_departments', [])

            # --- Contacts count (deduplicated) ---
            contact_ids = set()
            for sc in manual_contacts:
                contact_ids.add(sc.contact_id)
            for activity in activities:
                for contact in self._get_activity_prefetched_contacts(activity):
                    contact_ids.add(contact.id)

            # --- Departments list (deduplicated) ---
            departments = {}  # id -> {id, name}
            for sd in manual_departments:
                dept = sd.department
                if dept and dept.id not in departments:
                    departments[dept.id] = {
                        'id': str(dept.id),
                        'name': dept.get_name_display(),
                    }
            for activity in activities:
                for contact in self._get_activity_prefetched_contacts(activity):
                    dept = contact.standard_department
                    if dept and dept.id not in departments:
                        departments[dept.id] = {
                            'id': str(dept.id),
                            'name': dept.get_name_display(),
                        }

            # --- Effective dates ---
            effective_start = self._bulk_effective_start(activities)
            effective_end = self._bulk_effective_end(activities)

            results[step.id] = {
                'all_contacts_count': len(contact_ids),
                'all_departments_list': list(departments.values()),
                'effective_start_date': effective_start,
                'effective_end_date': effective_end,
            }

        return results

    # ------------------------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_source(contact_id, manual_ids, activity_ids):
        """Determine contact source for frontend badge display."""
        in_manual = contact_id in manual_ids
        in_activity = contact_id in activity_ids
        if in_manual and in_activity:
            return 'both'
        if in_manual:
            return 'manual'
        return 'activity'

    @staticmethod
    def _get_prefetched_activities(step):
        """Get activities from Django prefetch cache. Never triggers query."""
        cache = getattr(step, '_prefetched_objects_cache', {})
        return cache.get('activities', [])

    @staticmethod
    def _get_activity_prefetched_contacts(activity):
        """Get contacts from activity prefetch cache. Never triggers query."""
        cache = getattr(activity, '_prefetched_objects_cache', {})
        return cache.get('contacts', [])

    @staticmethod
    def _bulk_effective_start(activities):
        """Compute effective start from prefetched activities list."""
        # Priority 1: first completed activity date
        completed = [
            a for a in activities
            if a.status == 'COMPLETED' and a.completed_at
        ]
        if completed:
            first = min(completed, key=lambda a: a.completed_at)
            return first.completed_at.date()

        # Priority 2: first scheduled activity
        scheduled = [
            a for a in activities
            if a.scheduled_date
        ]
        if scheduled:
            first = min(scheduled, key=lambda a: a.scheduled_date)
            return first.scheduled_date

        return None

    @staticmethod
    def _bulk_effective_end(activities):
        """Compute effective end from prefetched activities list."""
        # Priority 1: last planned activity date
        planned_dates = []
        for a in activities:
            if a.status == 'PLANNED':
                date = a.due_date or a.scheduled_date
                if date:
                    planned_dates.append(date)
        if planned_dates:
            return max(planned_dates)

        # Priority 2: last completed activity date
        completed_dates = [
            a.completed_at.date()
            for a in activities
            if a.status == 'COMPLETED' and a.completed_at
        ]
        if completed_dates:
            return max(completed_dates)

        return None