# app_modules/decision_cycles/services/people_consolidation_service.py
"""
People Consolidation Service for Decision Cycles.

Provides a read-only consolidated view of all people involved in a
decision cycle, split into two groups:

  * qualified   — contacts/departments with a validated PeopleSignal
                  on this cycle (role, influence, notes are known)
  * unqualified — contacts who appear in cycle activities or step
                  contacts but have no PeopleSignal yet

No persistent DealStakeholder model — this is a computed view
assembled on each call. Stateless, no side effects.

Usage:
    service = PeopleConsolidationService()
    result = service.consolidate(decision_cycle)
    # result = {'qualified': [...], 'unqualified': [...]}
"""

from app_modules.signals.constants import SignalStatus


class PeopleConsolidationService:
    """
    Read-only consolidation of people involved in a DecisionCycle.

    Design:
    - Stateless: no stored state between calls.
    - Returns plain dicts (serializable).
    - No transaction.atomic — read-only queries.
    """

    def consolidate(self, decision_cycle):
        """
        Build the consolidated people view for a decision cycle.

        Args:
            decision_cycle: DecisionCycle instance.

        Returns:
            dict with:
              'qualified': list of dicts (one per validated PeopleSignal)
              'unqualified': list of dicts (contacts without a PeopleSignal)
        """
        qualified = self._get_qualified(decision_cycle)
        all_cycle_contacts = self._get_cycle_contacts(decision_cycle)

        qualified_contact_ids = {
            q['target_contact']['id']
            for q in qualified
            if q.get('target_contact')
        }

        unqualified = [
            c for c in all_cycle_contacts
            if str(c['contact']['id']) not in qualified_contact_ids
        ]

        return {
            'qualified': qualified,
            'unqualified': unqualified,
        }

    def _get_qualified(self, dc):
        """
        Validated PeopleSignals on this decision cycle.

        Returns a list of dicts with signal data + compact contact
        and department payloads.
        """
        from app_modules.signals.models import PeopleSignal

        signals = (
            PeopleSignal.objects
            .filter(decision_cycle=dc, status=SignalStatus.VALIDATED)
            .select_related('target_contact', 'target_department', 'source_activity')
            .order_by('role', '-created_at')
        )

        result = []
        for sig in signals:
            entry = {
                'signal_id': str(sig.id),
                'role': sig.role,
                'role_display': sig.get_role_display(),
                'influence': sig.influence,
                'influence_display': sig.get_influence_display() if sig.influence else None,
                'target_contact': self._compact_contact(sig.target_contact),
                'target_department': self._compact_department(sig.target_department),
                'notes': sig.notes,
                'status': sig.status,
                'created_at': sig.created_at.isoformat() if sig.created_at else None,
            }
            result.append(entry)
        return result

    def _get_cycle_contacts(self, dc):
        """
        All contacts appearing in cycle activities or step contacts.

        Sources:
          1. Activity.contacts M2M for activities where decision_cycle=dc
          2. DecisionStepContact for steps belonging to dc

        Returns deduplicated list of compact contact dicts with
        activity_count.
        """
        from app_modules.contacts.models import Contact
        from app_modules.activities.models import Activity
        from app_modules.decision_cycles.models import DecisionStepContact

        contact_activity_ids = set(
            Activity.objects
            .filter(decision_cycle=dc)
            .values_list('contacts__id', flat=True)
        )
        contact_activity_ids.discard(None)

        step_contact_ids = set(
            DecisionStepContact.objects
            .filter(step__cycle=dc)
            .values_list('contact_id', flat=True)
        )

        all_ids = contact_activity_ids | step_contact_ids
        if not all_ids:
            return []

        contacts = (
            Contact.objects
            .filter(id__in=all_ids)
            .select_related('standard_department')
        )

        activity_counts = {}
        for cid in all_ids:
            activity_counts[cid] = (
                Activity.objects
                .filter(decision_cycle=dc, contacts__id=cid)
                .count()
            )

        result = []
        for c in contacts:
            result.append({
                'contact': self._compact_contact(c),
                'department': self._compact_department(
                    getattr(c, 'standard_department', None)
                ),
                'activity_count': activity_counts.get(c.id, 0),
            })
        return result

    @staticmethod
    def _compact_contact(contact):
        if not contact:
            return None
        return {
            'id': str(contact.id),
            'first_name': contact.first_name,
            'last_name': contact.last_name,
            'job_title': getattr(contact, 'job_title', None),
        }

    @staticmethod
    def _compact_department(dept):
        if not dept:
            return None
        return {
            'id': str(dept.id),
            'name': dept.get_name_display(),
        }
