# app_modules/ai_pipelines/services/prep_call/input_pack_assembler.py
"""
PrepInputPackAssembler — assembles the deterministic input pack
consumed by the prep-call pipeline prompts.

Stateless, read-only, no LLM. Mirrors DealHealthEvidenceBuilder
but scoped to an Activity instead of a DecisionCycle.

The pack shape follows the contract defined in
guide/To_IMPLEMENT/signals_journey.md §3.2.
"""

import logging

from app_modules.signals.constants import SignalStatus

logger = logging.getLogger(__name__)


class PrepInputPackAssembler:
    """
    Assembles the prep-call input pack for an Activity.

    Usage:
        pack = PrepInputPackAssembler().build(
            activity=activity,
            brief_mode='CONVICTION',
        )
    """

    def build(self, *, activity, target_contact=None, brief_mode):
        """
        Build the input pack dict.

        Args:
            activity: Activity instance.
            target_contact: Contact instance or None.
            brief_mode: resolved brief mode string.

        Returns:
            dict matching the §3.2 Prep Input Pack contract.
        """
        dc = activity.decision_cycle

        maturity = self.build_maturity_snapshot(dc)
        signals = self._build_signals(dc) if dc else self._empty_signals()

        return {
            'prep_context': self._build_prep_context(
                activity, target_contact, dc,
            ),
            'maturity_snapshot': maturity,
            'levers': self._build_levers(signals),
            'stakeholder_focus': self._build_stakeholder_focus(
                target_contact, signals,
            ),
            'discovery_gaps': (
                maturity.get('dimensions', [])
                if maturity
                else []
            ),
            'competitive_context': self._build_competitive_context(signals),
            'evidence_scope': self._build_evidence_scope(dc, signals),
            'brief_mode': brief_mode,
        }

    # =========================================================================
    # PREP CONTEXT
    # =========================================================================

    def _build_prep_context(self, activity, target_contact, dc):
        ctx = {
            'account_name': str(activity.account) if activity.account else None,
            'upcoming_activity': {
                'type': activity.activity_type,
                'date': (
                    activity.scheduled_date.isoformat()
                    if activity.scheduled_date else None
                ),
                'primary_contact': (
                    self._serialize_contact_brief(target_contact)
                    if target_contact else None
                ),
            },
        }

        if dc:
            current_step = self._find_current_step(dc)
            ctx.update({
                'decision_cycle_id': str(dc.id),
                'current_step': current_step['name'] if current_step else None,
                'step_expectations': {
                    'goal': current_step.get('goal', '') if current_step else '',
                    'criterias': (
                        current_step.get('criterias', [])
                        if current_step else []
                    ),
                },
                'deal_value': (
                    str(dc.estimated_value) if dc.estimated_value else None
                ),
                'last_deal_health_snapshot_date': (
                    self._get_last_snapshot_date(dc)
                ),
            })
        else:
            ctx.update({
                'decision_cycle_id': None,
                'current_step': None,
                'step_expectations': {'goal': '', 'criterias': []},
                'deal_value': None,
                'last_deal_health_snapshot_date': None,
            })

        return ctx

    @staticmethod
    def _serialize_contact_brief(contact):
        from app_modules.signals.models import PeopleSignal

        role = None
        dept = contact.department or (
            contact.standard_department.get_name_display()
            if contact.standard_department else None
        )

        people = (
            PeopleSignal.objects
            .filter(
                target_contact=contact,
                status=SignalStatus.VALIDATED,
            )
            .order_by('-created_at')
            .first()
        )
        if people:
            role = people.role

        return {
            'id': str(contact.id),
            'role': role,
            'department': dept,
        }

    @staticmethod
    def _find_current_step(dc):
        steps = dc.steps.select_related('previous_step').order_by('order')
        for step in steps:
            if step.is_current:
                return {
                    'name': step.name,
                    'goal': step.goal or '',
                    'criterias': step.criterias or [],
                }
        return None

    @staticmethod
    def _get_last_snapshot_date(dc):
        from app_modules.decision_cycles.models import DealHealthSnapshot

        snapshot = (
            DealHealthSnapshot.objects
            .filter(decision_cycle=dc)
            .order_by('-snapshot_date', '-created_at')
            .first()
        )
        if not snapshot or not snapshot.snapshot_date:
            return None
        return snapshot.snapshot_date.isoformat()

    # =========================================================================
    # MATURITY SNAPSHOT
    # =========================================================================

    @staticmethod
    def build_maturity_snapshot(dc):
        """
        Extract the maturity snapshot from the latest DealHealthSnapshot.

        Public helper: called by the view to feed resolve_brief_mode()
        BEFORE build(), so the brief_mode can be passed into build().
        """
        if not dc:
            return None

        from app_modules.decision_cycles.models import DealHealthSnapshot

        snapshot = (
            DealHealthSnapshot.objects
            .filter(decision_cycle=dc)
            .order_by('-snapshot_date', '-created_at')
            .first()
        )
        if not snapshot:
            return None

        diagnostic = snapshot.diagnostic or {}
        return {
            'global_reading': diagnostic.get('global_reading', ''),
            'dimensions': diagnostic.get('dimensions', []),
        }

    # =========================================================================
    # SIGNALS — grouped for levers / stakeholder / competitive
    # =========================================================================

    def _build_signals(self, dc):
        from app_modules.signals.models import (
            PainSignal,
            ObjectiveSignal,
            ImpactSignal,
            TechStackSignal,
            BlockerSignal,
            ConstraintSignal,
            PeopleSignal,
        )

        validated = SignalStatus.VALIDATED

        return {
            'pain': list(
                PainSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).select_related('target_department').values(
                    'summary', 'source_quote', 'what', 'dimension',
                    'target_department__name',
                )
            ),
            'objective': list(
                ObjectiveSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).select_related(
                    'target_department', 'target_contact',
                ).values(
                    'summary', 'source_quote', 'what', 'dimension',
                    'target_department__name',
                )
            ),
            'impact': list(
                ImpactSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).select_related('target_department').values(
                    'summary', 'source_quote', 'what', 'dimension',
                    'impact_type', 'metric_text', 'human_impact',
                    'target_department__name',
                )
            ),
            # S10: tech identity lives on the signal's own columns, so
            # the catalogue FK is no longer joined. usage_department is
            # not read by _serialize_techstack_signals either.
            'techstack': self._serialize_techstack_signals(
                TechStackSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                )
            ),
            'blocker': self._serialize_blocker_signals(
                BlockerSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).select_related('contact')
            ),
            'constraint': list(
                ConstraintSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).select_related('target_department').values(
                    'summary', 'source_quote', 'what', 'dimension',
                    'rigidity', 'target_department__name',
                )
            ),
            'people': self._serialize_people_signals(
                PeopleSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).select_related('target_contact', 'target_department')
            ),
        }

    @staticmethod
    def _empty_signals():
        return {
            'pain': [],
            'objective': [],
            'impact': [],
            'techstack': [],
            'blocker': [],
            'constraint': [],
            'people': [],
        }

    @staticmethod
    def _serialize_techstack_signals(qs):
        """
        Tech rows, read entirely off the signal (S10).

        Was: label from str(tech_catalog_entry), flags from that
        catalogue row. The extractor no longer sets the FK, so every row
        came out {None, False, False} and _build_competitive_context
        below produced tools named "unknown" in the prompt.

        `is_to_replace` is new here — the catalogue had no equivalent.
        """
        # is_integration is intentionally NOT surfaced here: it was never
        # consumed by _build_competitive_context (which reads is_competitor /
        # is_to_replace only), and integration requirements are now TECHNICAL
        # constraints (surfaced through the constraint signals, not the tech row).
        return [
            {
                'tech_name': s.tech_name or '',
                'is_competitor': s.is_competitor,
                'is_to_replace': s.is_to_replace,
            }
            for s in qs
        ]

    @staticmethod
    def _serialize_blocker_signals(qs):
        return [
            {
                'summary': s.summary,
                'source_quote': s.source_quote or '',
                'contact_name': (
                    f"{s.contact.first_name} {s.contact.last_name}".strip()
                    if s.contact else None
                ),
            }
            for s in qs
        ]

    @staticmethod
    def _serialize_people_signals(qs):
        return [
            {
                'role': s.role,
                'influence': s.influence or '',
                'target_department': (
                    s.target_department.get_name_display()
                    if s.target_department else None
                ),
                'target_contact': (
                    f"{s.target_contact.first_name} {s.target_contact.last_name}".strip()
                    if s.target_contact else None
                ),
            }
            for s in qs
        ]

    # =========================================================================
    # LEVERS — derived from signals
    # =========================================================================

    @staticmethod
    def _build_levers(signals):
        desires = [
            {
                'summary': o['summary'],
                'department': o.get('target_department__name'),
                'theme': f"{o.get('what', '')} x {o.get('dimension', '')}",
            }
            for o in signals.get('objective', [])
        ]

        value = [
            {
                'summary': i['summary'],
                'department': i.get('target_department__name'),
                'theme': f"{i.get('what', '')} x {i.get('dimension', '')}",
            }
            for i in signals.get('impact', [])
            if i.get('metric_text')
        ]

        cost_frictions = [
            {'summary': b['summary'], 'actor': b.get('contact_name')}
            for b in signals.get('blocker', [])
        ]

        constraints = [
            {
                'summary': c['summary'],
                'department': c.get('target_department__name'),
                'rigidity': c.get('rigidity', ''),
            }
            for c in signals.get('constraint', [])
        ]

        return {
            'desires': desires,
            'value': value,
            'cost_frictions': cost_frictions,
            'constraints': constraints,
        }

    # =========================================================================
    # STAKEHOLDER FOCUS
    # =========================================================================

    @staticmethod
    def _build_stakeholder_focus(target_contact, signals):
        if not target_contact:
            return None

        contact_dept = target_contact.department or (
            target_contact.standard_department.get_name_display()
            if target_contact.standard_department else None
        )

        their_pains = [
            p['summary']
            for p in signals.get('pain', [])
            if p.get('target_department__name') == contact_dept and contact_dept
        ]

        their_desires = [
            o['summary']
            for o in signals.get('objective', [])
            if o.get('target_department__name') == contact_dept and contact_dept
        ]

        their_resistances = [
            b['summary']
            for b in signals.get('blocker', [])
        ]

        human_impacts = [
            {'type': i.get('human_impact'), 'self_reported': True}
            for i in signals.get('impact', [])
            if (
                i.get('human_impact')
                and i.get('target_department__name') == contact_dept
                and contact_dept
            )
        ]

        people_role = None
        for p in signals.get('people', []):
            if p.get('target_contact') == (
                f"{target_contact.first_name} {target_contact.last_name}".strip()
            ):
                people_role = p.get('role')
                break

        return {
            'contact_id': str(target_contact.id),
            'role': people_role,
            'department': contact_dept,
            'their_desires': their_desires,
            'their_pains': their_pains,
            'their_resistances': their_resistances,
            'human_impact': human_impacts,
        }

    # =========================================================================
    # COMPETITIVE CONTEXT
    # =========================================================================

    @staticmethod
    def _build_competitive_context(signals):
        """
        Split the account's tooling into commercial buckets.

        S10: reads `tech_name` (was `catalog_name`, derived from the
        TechCatalog FK the extractor no longer sets — every tool was
        rendering as "unknown" in the prompt).

        `to_replace` is a NEW bucket, not a partition of the other two: a
        tool the account intends to drop is an open door whether or not
        we compete with it, so a competitor slated for replacement
        legitimately appears in both `competing_on_deal` and `to_replace`.
        `incumbents` and `competing_on_deal` stay mutually exclusive, as
        before.
        """
        techstack = signals.get('techstack', [])
        return {
            'incumbents': [
                {'tool': t['tech_name'], 'is_competitor': t['is_competitor']}
                for t in techstack
                if not t.get('is_competitor')
            ],
            'competing_on_deal': [
                {'tool': t['tech_name'], 'is_competitor': True}
                for t in techstack
                if t.get('is_competitor')
            ],
            'to_replace': [
                {'tool': t['tech_name'], 'is_competitor': t['is_competitor']}
                for t in techstack
                if t.get('is_to_replace')
            ],
        }

    # =========================================================================
    # EVIDENCE SCOPE
    # =========================================================================

    @staticmethod
    def _build_evidence_scope(dc, signals):
        total = sum(len(v) for v in signals.values())

        transcripts_count = 0
        if dc:
            from app_modules.activities.models import Activity
            transcripts_count = (
                Activity.objects
                .filter(
                    decision_cycle=dc,
                    activity_type__in=('CALL', 'MEETING', 'DEMO'),
                    status='COMPLETED',
                )
                .count()
            )

        return {
            'validated_signals_count': total,
            'transcripts_count': transcripts_count,
            'coverage_note': 'Based on captured evidence.',
        }
