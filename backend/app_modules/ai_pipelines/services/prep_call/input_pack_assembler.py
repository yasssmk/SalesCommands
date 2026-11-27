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

from app_modules.ai_pipelines.constants import (
    DEAL_HEALTH_TRUNCATION_MARKER,
    PREP_CALL_MAX_CHARS_PER_SOURCE,
    PREP_CALL_PREVIOUS_ACTIVITIES_MAX,
    people_role_for_prompt,
)
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
        assembler = PrepInputPackAssembler()
        pack = assembler.build(activity=activity)
        assembler.people   # the activity's roster (G4), for the validation

    No brief mode since G10 (a single Game Plan mode — the mode resolver is
    removed).
    """

    people = None
    recipients_omitted = 0

    def build(self, *, activity, target_contact=None, language_overrides=None):
        """
        Build the input pack dict.

        Args:
            activity: Activity instance.
            target_contact: Contact instance or None.
            language_overrides: [{'ref', 'language'}] — the languages chosen
                for this generation of an AI message (G11), tags validated.

        Returns:
            dict matching the §3.2 Prep Input Pack contract. The roster the
            pack's labels come from is kept on `self.people` (G10: the
            server-side resolution of the refs the Game Plan writes back —
            the deal health's `builder.roster` pattern).
        """
        dc = activity.decision_cycle

        # G4: ONE roster for the whole prompt — the cycle's people and the
        # activity's participants, every label final before it is read.
        people = activity_roster(activity)
        self.people = people
        # G7: read ONCE for the whole pack — the cycle's current step (S5),
        # its latest deal-health snapshot (S3), its validated objectives.
        current_step = self._current_step(dc) if dc else None
        dh_snapshot = DealHealthEvidenceBuilder.latest_snapshot(dc) if dc else None
        objectives = self._validated_objectives(dc) if dc else []
        maturity = self._maturity_of(dh_snapshot)
        signals = (
            self._build_signals(dc, people.roster, objectives) if dc else self._empty_signals()
        )

        return {
            'prep_context': self._build_prep_context(
                activity, target_contact, dc, current_step, dh_snapshot,
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
            # G4 (TD-46 / TD-48): every participant, by its label — the ids
            # stay server-side (never rendered), no last name, email or phone.
            'participants': [
                {key: p[key] for key in (
                    'label', 'role', 'department', 'profile', 'contact_id', 'stakeholder_id',
                )}
                for p in people.participants
            ],
            # ---- G7: the input pack v2 — what exists, read, never recalculated.
            'deal_health': self._build_deal_health(dh_snapshot),
            'activity': self._build_activity(activity),
            'objectives': DealHealthEvidenceBuilder.serialize_objective_signals(objectives),
            'deal': (
                DealHealthEvidenceBuilder().build_cycle_context(dc, current_step) if dc else None
            ),
            'account': (
                DealHealthEvidenceBuilder.account_context(activity.account)
                if activity.account_id else None
            ),
            'manager_notes': [
                {**note, 'content': _bounded(note['content'])}
                for note in (DealHealthEvidenceBuilder.manager_notes(dc) if dc else [])
            ],
            'seller_profile': self._build_seller_profile(activity.client_id),
            'previous_activities': self._build_previous_activities(activity),
            # G8: the light campaign diagnostic's data — ONLY outside a cycle
            # (a campaign activity inside a cycle keeps the DC path).
            'campaign': (
                self._build_campaign(activity)
                if activity.campaign_id and not activity.decision_cycle_id else None
            ),
            # G11: the recipients of an AI message (an email / a LinkedIn
            # message) and their language — None for a conversation.
            'recipients': self._build_recipients(activity, people, language_overrides),
        }

    def _build_recipients(self, activity, people, language_overrides):
        """The recipients of an AI message (services/prep_call/
        message_language.message_recipients — Q2 / Q3 / Q7), None for a
        conversation. Raises the standard 400 for an override to an unknown
        recipient."""
        from app_modules.ai_pipelines.constants import PREP_CALL_MESSAGE_TYPES
        from app_modules.ai_pipelines.services.prep_call.message_language import (
            message_recipients,
        )
        if activity.activity_type not in PREP_CALL_MESSAGE_TYPES:
            return None
        recipients, self.recipients_omitted = message_recipients(people, language_overrides)
        return recipients

    # =========================================================================
    # PREP CONTEXT
    # =========================================================================

    def _build_prep_context(self, activity, target_contact, dc, current_step, dh_snapshot):
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
            current_step = self._step_dict(current_step)
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
                    dh_snapshot.snapshot_date.isoformat()
                    if dh_snapshot is not None and dh_snapshot.snapshot_date else None
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
    def _current_step(dc):
        """The cycle's current step, derived ONCE for the whole cycle
        (current_decision_step — the shared definition of
        DecisionStep.is_current) instead of one is_current per step, each
        re-deriving the cycle (sprint 2 Game Plan, S5; the deal health's
        evidence builder does the same). G7: derived once for the whole pack
        (the prep context AND the deal context)."""
        from app_modules.activities.services.next_step_materialization import (
            current_decision_step,
        )
        return current_decision_step(dc)

    @staticmethod
    def _step_dict(step):
        if step is None:
            return None
        return {
            'name': step.name,
            'goal': step.goal or '',
            'criterias': step.criterias or [],
        }

    # =========================================================================
    # MATURITY SNAPSHOT
    # =========================================================================

    @staticmethod
    def _maturity_of(snapshot):
        """The v1 maturity view of a deal-health snapshot (or None)."""
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

    def _build_signals(self, dc, roster, objectives):
        # Every person is named by llm_people (first name only, homonyms told
        # apart) — ONE roster for the prompt (sprint « Deal health v2 », 3a;
        # since G4 the activity's roster, participants included).
        from app_modules.signals.models import (
            PainSignal,
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
            # The validated objectives, read ONCE for the pack (G7) — the v1
            # rows (levers / stakeholder focus) and the v2 `objectives` block
            # come from the same instances.
            'objective': [
                {
                    'summary': o.summary,
                    'source_quote': o.source_quote,
                    'what': o.what,
                    'dimension': o.dimension,
                    'target_department__name': (
                        o.target_department.name if o.target_department_id else None
                    ),
                }
                for o in objectives
            ],
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

    # =========================================================================
    # INPUT PACK v2 (sprint 2 Game Plan, G7) — read the existing, recalculate nothing
    # =========================================================================

    # The deal-health v2 keys the Game Plan reads (diagnostic_v2.py schema).
    _DEAL_HEALTH_V2_KEYS = (
        'summary', 'strategic_conclusion', 'objectives', 'missing_info',
        'top_arguments', 'stakeholders', 'bant', 'needs_and_urgency',
        'credibility', 'fit_and_value', 'estimated_step',
    )

    @staticmethod
    def _validated_objectives(dc):
        """The cycle's validated Objective signals — ONE query, shared by the
        v1 levers and the v2 `objectives` block."""
        from app_modules.signals.models import ObjectiveSignal
        return list(
            ObjectiveSignal.objects
            .filter(decision_cycle=dc, client_id=dc.client_id, status=SignalStatus.VALIDATED)
            .select_related('target_department')
            .order_by('created_at', 'id')
        )

    @classmethod
    def _build_deal_health(cls, snapshot):
        """The latest deal-health snapshot as the Game Plan reads it: its trace
        (snapshot_id + schema_version) and its v2 keys (None when absent — a
        v1 snapshot). None without a snapshot."""
        if snapshot is None:
            return None
        diagnostic = snapshot.diagnostic or {}
        return {
            'snapshot_id': str(snapshot.id),
            'schema_version': snapshot.schema_version,
            'snapshot_date': snapshot.snapshot_date.isoformat() if snapshot.snapshot_date else None,
            **{key: diagnostic.get(key) for key in cls._DEAL_HEALTH_V2_KEYS},
        }

    @staticmethod
    def _build_activity(activity):
        """The activity being prepared: its own content, bounded."""
        return {
            'type': activity.activity_type,
            'date': activity.scheduled_date.isoformat() if activity.scheduled_date else None,
            'description': _bounded(activity.description),
            'call_to_action': _bounded(activity.call_to_action),
            'outcome_notes': _bounded(activity.outcome_notes),
            'preparation_notes': _bounded(activity.preparation_notes),
        }

    @staticmethod
    def _build_seller_profile(client_id):
        """The tenant's seller profile (G6) — None when none yet. Its
        updated_at is carried for the dedup hash only."""
        from app_modules.product_catalog.models import SellerProfile
        profile = SellerProfile.objects.filter(client_id=client_id).first()
        if profile is None:
            return None
        return {
            'company_description': _bounded(profile.company_description),
            'value_proposition': _bounded(profile.value_proposition),
            'customer_references': profile.customer_references or [],
            'credibility_and_certifications': _bounded(profile.credibility_and_certifications),
            'competitors_and_positioning': _bounded(profile.competitors_and_positioning),
            'ideal_targets': _bounded(profile.ideal_targets),
            'updated_at': profile.updated_at.isoformat() if profile.updated_at else None,
        }

    @staticmethod
    def _build_previous_activities(activity):
        """The previous conversations (PO decision Q5): the COMPLETED
        activities of the same cycle OR of the same sequence (campaign
        contact), this one excluded, the PREP_CALL_PREVIOUS_ACTIVITIES_MAX most
        recent — ONE query — returned oldest first, their notes bounded."""
        from django.db.models import Q

        from app_modules.activities.constants import ActivityStatus
        from app_modules.activities.models import Activity

        scope = Q()
        if activity.decision_cycle_id:
            scope |= Q(decision_cycle_id=activity.decision_cycle_id)
        if activity.campaign_contact_id:
            scope |= Q(campaign_contact_id=activity.campaign_contact_id)
        if not scope:
            return []
        rows = list(
            Activity.objects
            .filter(scope, client_id=activity.client_id, account_id=activity.account_id,
                    status=ActivityStatus.COMPLETED)
            .exclude(pk=activity.pk)
            .defer('transcript')
            .order_by('-completed_at', '-scheduled_date', '-created_at')[:PREP_CALL_PREVIOUS_ACTIVITIES_MAX]
        )
        return [
            {
                'type': a.activity_type,
                'date': DealHealthEvidenceBuilder.activity_moment(a).date().isoformat(),
                'description': _bounded(a.description),
                'outcome': a.get_outcome_display() if a.outcome else '',
                'notes': _bounded(a.outcome_notes),
            }
            for a in reversed(rows)
        ]


    @staticmethod
    def _build_campaign(activity):
        """
        The campaign of an activity outside a cycle (G8): the campaign's
        objective (activity_objective), the contact's objective and status
        (CampaignContact), the sequence — position / total and the next open
        steps, ActivitySequenceService.get_sequence_context(activity,
        SequenceScope.CAMPAIGN), reused. The activity's call_to_action (the
        stored result of campaign_execution_service._create_activity's
        objective copy) is in `activity`; the history and results of the
        sequence are `previous_activities` (same sequence) — neither is read
        twice nor recomputed.
        """
        from app_modules.activities.services.activity_sequence_service import (
            ActivitySequenceService,
            SequenceScope,
        )

        campaign = activity.campaign
        contact = activity.campaign_contact if activity.campaign_contact_id else None
        sequence = ActivitySequenceService.get_sequence_context(
            activity, SequenceScope.CAMPAIGN,
        ) or {}
        return {
            'name': campaign.name,
            'type': campaign.get_campaign_type_display(),
            'objective': _bounded(campaign.activity_objective),
            'contact_objective': _bounded(contact.objective) if contact else '',
            'contact_status': contact.status if contact else None,
            'sequence': {
                'position': sequence.get('position'),
                'total': sequence.get('total'),
                'next_steps': [
                    {
                        'type': step.get('activity_type'),
                        'status': step.get('status'),
                        'scheduled_date': step.get('scheduled_date'),
                    }
                    for step in sequence.get('next_activities') or []
                ],
            },
        }

def _bounded(text):
    """A free text of the pack, cut to PREP_CALL_MAX_CHARS_PER_SOURCE (the deal
    health's bound) with its truncation marker; '' for none."""
    text = text or ''
    if len(text) <= PREP_CALL_MAX_CHARS_PER_SOURCE:
        return text
    return (
        text[:PREP_CALL_MAX_CHARS_PER_SOURCE] + '\n'
        + DEAL_HEALTH_TRUNCATION_MARKER.format(kept=PREP_CALL_MAX_CHARS_PER_SOURCE, total=len(text))
    )
