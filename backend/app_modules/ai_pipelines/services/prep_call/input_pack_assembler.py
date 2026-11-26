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

from app_modules.ai_pipelines.constants import people_role_for_prompt
from app_modules.ai_pipelines.services.deal_health_evidence_builder import (
    DealHealthEvidenceBuilder,
)
from app_modules.ai_pipelines.services.llm_people import activity_roster
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

        # G4: ONE roster for the whole prompt — the cycle's people and the
        # activity's participants, every label final before it is read.
        people = activity_roster(activity)
        maturity = self.build_maturity_snapshot(dc)
        signals = self._build_signals(dc, people.roster) if dc else self._empty_signals()

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
            # G4 (TD-46 / TD-48): every participant, by its label — the ids
            # stay server-side (never rendered), no last name, email or phone.
            'participants': [
                {key: p[key] for key in (
                    'label', 'role', 'department', 'profile', 'contact_id', 'stakeholder_id',
                )}
                for p in people.participants
            ],
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
            role = people_role_for_prompt(people.role)

        return {
            'id': str(contact.id),
            'role': role,
            'department': dept,
        }

    @staticmethod
    def _find_current_step(dc):
        """The cycle's current step, derived ONCE for the whole cycle
        (current_decision_step — the shared definition of
        DecisionStep.is_current) instead of one is_current per step, each
        re-deriving the cycle (sprint 2 Game Plan, S5; the deal health's
        evidence builder does the same)."""
        from app_modules.activities.services.next_step_materialization import (
            current_decision_step,
        )
        step = current_decision_step(dc)
        if step is None:
            return None
        return {
            'name': step.name,
            'goal': step.goal or '',
            'criterias': step.criterias or [],
        }

    @staticmethod
    def _get_last_snapshot_date(dc):
        # The canonical reader, inside the tenant (sprint 2 Game Plan, S3).
        snapshot = DealHealthEvidenceBuilder.latest_snapshot(dc)
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

        # The canonical reader, inside the tenant (sprint 2 Game Plan, S3).
        snapshot = DealHealthEvidenceBuilder.latest_snapshot(dc)
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

    def _build_signals(self, dc, roster):
        # Every person is named by llm_people (first name only, homonyms told
        # apart) — ONE roster for the prompt (sprint « Deal health v2 », 3a;
        # since G4 the activity's roster, participants included).
        from app_modules.signals.models import (
            PainSignal,
            ObjectiveSignal,
            ImpactSignal,
            TechStackSignal,
            BlockerSignal,
            ConstraintSignal,
            CompetitorSignal,
            PeopleSignal,
        )

        validated = SignalStatus.VALIDATED

        # The deal's competitors, ONE query: their names for the competitor
        # facet below, their normalised names for the TechStack rows'
        # competitor marker (S6).
        competitors = list(
            CompetitorSignal.objects.filter(
                decision_cycle=dc, status=validated,
            ).values('competitor_name', 'competitor_name_normalized')
        )

        return {
            # Multi-department scope (sub-step 2b): read WHO the pain concerns
            # off the target_departments M2M, not the legacy FK. A
            # .values('target_department__name') join would multiply rows, so
            # iterate instances with the M2M prefetched and aggregate the names.
            'pain': [
                {
                    'summary': p.summary,
                    'source_quote': p.source_quote,
                    'what': p.what,
                    'dimension': p.dimension,
                    'department_names': [
                        d.get_name_display() for d in p.target_departments.all()
                    ],
                }
                for p in PainSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).prefetch_related('target_departments')
            ],
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
            # Multi-department scope (sub-step 2b): same M2M treatment as pain.
            'impact': [
                {
                    'summary': i.summary,
                    'source_quote': i.source_quote,
                    'what': i.what,
                    'dimension': i.dimension,
                    'impact_type': i.impact_type,
                    'metric_text': i.metric_text,
                    'human_impact': i.human_impact,
                    'department_names': [
                        d.get_name_display() for d in i.target_departments.all()
                    ],
                }
                for i in ImpactSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).prefetch_related('target_departments')
            ],
            # TD-314 (sprint 2 Game Plan, S6): the deal health's own TechStack
            # rows (step 3b) — tool, usage scope + departments, discontinuation
            # (« no longer used » / « planned exit », ai_pipelines/constants.py),
            # competitor marker — reused as they are, not re-serialised here.
            # `is_to_replace` is no longer read (as the deal health).
            'techstack': DealHealthEvidenceBuilder.serialize_techstack_signals(
                TechStackSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).prefetch_related('usage_departments'),
                frozenset(c['competitor_name_normalized'] for c in competitors),
            ),
            'blocker': self._serialize_blocker_signals(
                BlockerSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).select_related('contact'),
                roster,
            ),
            # Multi-department scope (sub-step 1b): read WHO the constraint
            # concerns off the target_departments M2M, not the legacy FK. A
            # .values('target_department__name') join would multiply rows (one
            # per department), so iterate instances with the M2M prefetched and
            # aggregate the names into a per-signal list.
            'constraint': [
                {
                    'summary': c.summary,
                    'source_quote': c.source_quote,
                    'what': c.what,
                    'dimension': c.dimension,
                    'rigidity': c.rigidity,
                    'department_names': [
                        d.get_name_display() for d in c.target_departments.all()
                    ],
                }
                for c in ConstraintSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).prefetch_related('target_departments')
            ],
            # Sub-step 4: the competitor facet is now sourced from the
            # detached CompetitorSignal (DC-scoped + VALIDATED), cloned on
            # the ConstraintSignal read above — NOT from TechStackSignal
            # .is_competitor. Each row is a competitor on this deal.
            'competitor': [
                {'competitor_name': c['competitor_name']} for c in competitors
            ],
            'people': self._serialize_people_signals(
                PeopleSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).select_related('target_contact', 'target_department'),
                roster,
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
            'competitor': [],
            'people': [],
        }

    @staticmethod
    def _serialize_blocker_signals(qs, roster):
        return [
            {
                'summary': s.summary,
                'source_quote': s.source_quote or '',
                # llm_people label (first name only).
                'contact_name': roster.label(s.contact) if s.contact else None,
            }
            for s in qs
        ]

    @staticmethod
    def _serialize_people_signals(qs, roster):
        return [
            {
                'role': people_role_for_prompt(s.role),
                'influence': s.influence or '',
                'target_department': (
                    s.target_department.get_name_display()
                    if s.target_department else None
                ),
                # llm_people label (first name only).
                'target_contact': roster.label(s) if s.target_contact else None,
                # Server-side match of the target contact (never rendered).
                'target_contact_id': (
                    str(s.target_contact_id) if s.target_contact_id else None
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
                # Multi-department (sub-step 2b): list of concerned departments
                # (a mono-department impact yields a 1-element list).
                'departments': i.get('department_names', []),
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
                # Multi-department (sub-step 1b): the list of concerned
                # departments (a mono-department constraint yields a 1-element
                # list, preserving the previous information).
                'departments': c.get('department_names', []),
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
            # Multi-department (sub-step 2b): match if the contact's department
            # is among the pain's concerned departments.
            if contact_dept and contact_dept in p.get('department_names', [])
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
                # Multi-department (sub-step 2b): contact's department among the
                # impact's concerned departments.
                and contact_dept
                and contact_dept in i.get('department_names', [])
            )
        ]

        # Matched on the contact id (was: on the full name string, which the
        # pack no longer carries — sprint « Deal health v2 », step 3a).
        people_role = None
        for p in signals.get('people', []):
            if p.get('target_contact_id') == str(target_contact.id):
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
        Split the deal's tooling into commercial buckets.

        Sub-step 4 recabling — the SOURCE of the competitor facet changed,
        the OUTPUT shape did not:
          * `competing_on_deal` is now built from the detached
            CompetitorSignal (`signals['competitor']`, DC-scoped + VALIDATED
            upstream), tool <- competitor_name. TechStackSignal.is_competitor
            is no longer consulted here.
          * `incumbents` is REDEFINED as the account's tooling on the deal —
            every TechStackSignal — with NO reference to is_competitor. A tool
            can now be both an incumbent (it is in place) and a competitor (a
            CompetitorSignal names it): the three buckets are non-exclusive by
            design.
          * TD-314 (sprint 2 Game Plan, S6): each incumbent carries its usage
            (`usage_scope`, `usage_departments`) and its discontinuation
            (`discontinued`: None / « no longer used » / « planned exit »,
            `discontinued_date`) — straight from the deal health's TechStack
            rows. The `to_replace` bucket is gone: is_to_replace is no longer
            read (always False on extraction; the deal health dropped it at
            its step 3b).

        prompts/prep_call/context.py only prints what these entries give.
        """
        techstack = signals.get('techstack', [])
        competitors = signals.get('competitor', [])
        return {
            'incumbents': [
                {
                    'tool': t['tech_name'],
                    'usage_scope': t.get('usage_scope'),
                    'usage_departments': t.get('usage_departments', []),
                    'discontinued': t.get('discontinued'),
                    'discontinued_date': t.get('discontinued_date', ''),
                }
                for t in techstack
            ],
            'competing_on_deal': [
                {'tool': c['competitor_name']}
                for c in competitors
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
