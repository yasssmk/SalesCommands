# app_modules/ai_pipelines/services/deal_health_evidence_builder.py
"""
DealHealthEvidenceBuilder — assembles the deterministic evidence pack
consumed by the deal-health pipeline prompts.

Stateless, read-only, no LLM. Queries validated signals by type,
readiness score, people consolidation, cycle context (step, products),
and the previous snapshot.

Sprint « Deal health v2 », step 3b — ALL the sources, only the NEW ones:
the activities of the cycle (transcript / email content, notes,
description, objective, outcome — analysed or not), the validated signals
and the ManagerNotes that changed since the last snapshot's sources_cursor
(none on a first pass, or after a v1 snapshot: everything is read). The pack
returns the NEW cursor (persisted by DealHealthWriter) and the static
context sent every time (account, deal, origin campaign, products). Input
bounds and truncation: constants.DEAL_HEALTH_MAX_*.

The pack shape is the contract between this builder, the context layer,
and the diagnostic request layer.
"""

import logging

from django.db.models import Max
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from app_modules.ai_pipelines.constants import (
    DEAL_HEALTH_CURSOR_STAKEHOLDERS,
    DEAL_HEALTH_CURSOR_STATIC_CONTEXT,
    DEAL_HEALTH_FRESHNESS_NEW_SOURCES,
    DEAL_HEALTH_FRESHNESS_NO_ANALYSIS_YET,
    DEAL_HEALTH_FRESHNESS_STAKEHOLDERS_CHANGED,
    DEAL_HEALTH_FRESHNESS_STEP_CHANGED,
    DEAL_HEALTH_CURSOR_ACTIVITIES,
    DEAL_HEALTH_CURSOR_MANAGER_NOTES,
    DEAL_HEALTH_CURSOR_SIGNALS,
    DEAL_HEALTH_MAX_CHARS_PER_SOURCE,
    DEAL_HEALTH_MAX_INPUT_CHARS,
    DEAL_HEALTH_NOTE_AUTHOR_ADMIN,
    DEAL_HEALTH_NOTE_AUTHOR_MANAGER,
    DEAL_HEALTH_TRUNCATION_INPUT_BUDGET,
    DEAL_HEALTH_TRUNCATION_MARKER,
    DEAL_HEALTH_TRUNCATION_PER_SOURCE,
    PEOPLE_ROLE_TO_QUALIFY,
    TECHSTACK_NO_LONGER_USED,
    TECHSTACK_PLANNED_EXIT,
    people_role_for_prompt,
)
from app_modules.ai_pipelines.services.llm_people import (
    cycle_roster,
    stakeholder_for,
    stakeholder_prompt_facts,
)
from app_modules.signals.constants import PeopleRole, SignalStatus

from app_modules.decision_cycles.services.readiness_score_service import (
    ReadinessScoreService,
)
from app_modules.decision_cycles.services.people_consolidation_service import (
    PeopleConsolidationService,
)
from app_modules.decision_cycles.constants import DEAL_HEALTH_SCHEMA_V2


logger = logging.getLogger(__name__)


class DealHealthEvidenceBuilder:
    """
    Assembles the evidence pack for a DecisionCycle.

    Usage:
        pack = DealHealthEvidenceBuilder().build(decision_cycle)
    """

    # Input bounds (amendment A3) — the constants, exposed as class
    # attributes (the pipelines/base.py CONFIDENCE_MIN pattern).
    MAX_CHARS_PER_SOURCE = DEAL_HEALTH_MAX_CHARS_PER_SOURCE
    MAX_INPUT_CHARS = DEAL_HEALTH_MAX_INPUT_CHARS

    def build(self, decision_cycle):
        """
        Build the evidence pack dict.

        Args:
            decision_cycle: DecisionCycle instance.

        Returns:
            dict with keys: cycle, account, readiness, people, signals,
            activities, manager_notes, previous_snapshot (static context and
            NEW evidence), sources_cursor (the cursor after this read) and
            truncation (None, or the trace of the input bounds applied).
        """
        dc = decision_cycle
        # ONE roster for the whole prompt: every person is named by
        # llm_people (first name only, homonyms told apart — sprint « Deal
        # health v2 », step 3a), the same label wherever they appear.
        roster = self._build_roster(dc)
        # Kept for the writer (step 5): the labels the LLM writes back are
        # resolved against THIS roster, server side.
        self.roster = roster

        previous = self._latest_snapshot(dc)
        # Kept for the run guard (step 6, A10): with a previous snapshot and
        # nothing new (new_info_reasons, S7), the run stops before the LLM.
        self.previous_snapshot = previous
        since = self._parse_cursor(previous.sources_cursor if previous else None)

        signals, signals_at = self._build_signals(dc, roster, since.get(DEAL_HEALTH_CURSOR_SIGNALS))
        activities, activities_at = self._build_activities(dc, since.get(DEAL_HEALTH_CURSOR_ACTIVITIES))
        notes, notes_at = self._build_manager_notes(dc, since.get(DEAL_HEALTH_CURSOR_MANAGER_NOTES))
        truncation = self._apply_input_bounds(activities, signals, notes)
        cycle_context = self._build_cycle_context(dc)
        account_context = self._build_account_context(dc)
        sources_cursor = self._next_cursor(since, {
            DEAL_HEALTH_CURSOR_ACTIVITIES: activities_at,
            DEAL_HEALTH_CURSOR_SIGNALS: signals_at,
            DEAL_HEALTH_CURSOR_MANAGER_NOTES: notes_at,
        })
        # 6c: the static context, fingerprinted from the SAME blocks as the
        # prompt's — a change there is new.
        sources_cursor[DEAL_HEALTH_CURSOR_STATIC_CONTEXT] = self.static_fingerprint(
            cycle_context, account_context,
        )
        # S7 (PO Q4): the stakeholders — a removal included, which no
        # timestamp cursor can see.
        sources_cursor[DEAL_HEALTH_CURSOR_STAKEHOLDERS] = self.stakeholders_fingerprint(dc)

        return {
            'cycle': cycle_context,
            'account': account_context,
            'readiness': ReadinessScoreService().calculate(dc),
            'people': self._build_people(dc, roster),
            'stakeholders': self._build_stakeholders(dc, roster),
            'signals': signals,
            'activities': activities,
            'manager_notes': notes,
            'previous_snapshot': self._build_previous_snapshot(previous),
            'sources_cursor': sources_cursor,
            'truncation': truncation,
        }

    # =========================================================================
    # SOURCES CURSOR (step 3b)
    # =========================================================================

    # -- THE filters of the new sources (one source of truth, step 8) --------
    # The prompt's reads (_build_signals / _build_activities /
    # _build_manager_notes) and the « is there anything new? » test
    # (new_info_reasons: the run guard A10 and the read-time freshness) use
    # these querysets, never a copy of their filters.

    @staticmethod
    def signal_models():
        """The validated signal types the deal health reads."""
        from app_modules.signals.models import (
            BlockerSignal, CompetitorSignal, ConstraintSignal, ImpactSignal,
            ObjectiveSignal, PainSignal, PeopleSignal, TechStackSignal,
        )
        return (PainSignal, ObjectiveSignal, ImpactSignal, TechStackSignal,
                BlockerSignal, ConstraintSignal, PeopleSignal, CompetitorSignal)

    @staticmethod
    def fresh_signals_qs(model, dc, since=None):
        """The validated signals of `model` changed after `since` (all when None)."""
        qs = model.objects.filter(decision_cycle=dc, status=SignalStatus.VALIDATED)
        return qs.filter(updated_at__gt=since) if since is not None else qs

    @classmethod
    def fresh_activities_qs(cls, dc, since=None):
        """The activities of the cycle carrying content (_ACTIVITY_TEXT_FIELDS)
        changed after `since` (all when None)."""
        from django.db.models import Q
        from app_modules.activities.models import Activity

        has_content = Q()
        for field in cls._ACTIVITY_TEXT_FIELDS:
            has_content |= (Q(**{f'{field}__isnull': False}) & ~Q(**{field: ''}))
        qs = (
            Activity.objects
            .filter(decision_cycle=dc, client_id=dc.client_id)
            .filter(has_content)
        )
        return qs.filter(updated_at__gt=since) if since is not None else qs

    @staticmethod
    def fresh_manager_notes_qs(dc, since=None):
        """The ManagerNotes of the cycle created after `since` (all when None)."""
        from app_modules.decision_cycles.models import ManagerNote
        qs = ManagerNote.objects.filter(decision_cycle=dc, client_id=dc.client_id)
        return qs.filter(created_at__gt=since) if since is not None else qs

    def new_info_reasons(self, dc, previous, current_stage):
        """
        THE « is there new information? » predicate of a deal health (sprint
        2 Game Plan, S7) — read by the run guard (A10: no reason, no run) AND
        by the read-time freshness (the DC banner), never two copies, so a
        reason is present <=> the re-run is accepted.

        Args:
            dc:            the DecisionCycle.
            previous:      its last DealHealthSnapshot, or None.
            current_stage: the stage of its current step (or None).

        Returns:
            [reasons], in this order:
              NO_ANALYSIS_YET      — no previous snapshot;
              NEW_SOURCES          — since the snapshot: an ANALYSED activity
                                     (a successful extraction), a validated
                                     signal, a manager note, or another
                                     static-context fingerprint;
              STEP_CHANGED         — the current step's stage differs from the
                                     snapshot's declared_step (ignored when
                                     that one is NULL — the v1 snapshots);
              STAKEHOLDERS_CHANGED — another stakeholders fingerprint (ignored
                                     when the snapshot has none — before S7).
            A note typed on an activity, or any edit of an activity, is NEVER
            a reason by itself. EXISTENCE queries only: bounded.
        """
        if previous is None:
            return [DEAL_HEALTH_FRESHNESS_NO_ANALYSIS_YET]
        cursor = previous.sources_cursor or {}
        reasons = []
        if self._has_new_sources(dc, previous, cursor):
            reasons.append(DEAL_HEALTH_FRESHNESS_NEW_SOURCES)
        if previous.declared_step and previous.declared_step != current_stage:
            reasons.append(DEAL_HEALTH_FRESHNESS_STEP_CHANGED)
        stored = cursor.get(DEAL_HEALTH_CURSOR_STAKEHOLDERS)
        if stored is not None and stored != self.stakeholders_fingerprint(dc):
            reasons.append(DEAL_HEALTH_FRESHNESS_STAKEHOLDERS_CHANGED)
        return reasons

    def _has_new_sources(self, dc, previous, cursor):
        """NEW_SOURCES of new_info_reasons: an analysed activity of the cycle
        since the snapshot's date, a validated signal / a manager note since
        their cursor, or (6c) another static-context fingerprint. Activities
        merely edited (fresh_activities_qs) are NOT read here — the prompt
        still reads them when a run happens."""
        from .analysis_state import analysed_runs_of_cycle

        since = self._parse_cursor(cursor)
        if analysed_runs_of_cycle(dc, previous.snapshot_date).exists():
            return True
        if self.fresh_manager_notes_qs(dc, since.get(DEAL_HEALTH_CURSOR_MANAGER_NOTES)).exists():
            return True
        signals_since = since.get(DEAL_HEALTH_CURSOR_SIGNALS)
        if any(self.fresh_signals_qs(model, dc, signals_since).exists()
               for model in self.signal_models()):
            return True
        fingerprint = self.static_fingerprint(
            self._build_cycle_context(dc), self._build_account_context(dc),
        )
        return fingerprint != cursor.get(DEAL_HEALTH_CURSOR_STATIC_CONTEXT)

    @staticmethod
    def stakeholders_fingerprint(dc):
        """S7 (PO Q4): sha256 of the cycle's stakeholders — each one's id and
        the role of its current signal (the role is never copied on the
        stakeholder: read on current_signal)."""
        import hashlib
        import json

        from app_modules.decision_cycles.models import Stakeholder

        rows = sorted(
            [str(pk), role or '']
            for pk, role in Stakeholder.objects
            .filter(decision_cycle=dc, client_id=dc.client_id)
            .values_list('id', 'current_signal__role')
        )
        return hashlib.sha256(json.dumps(rows).encode('utf-8')).hexdigest()

    @staticmethod
    def static_fingerprint(cycle_context, account_context):
        """6c: sha256 of the static context blocks of the prompt (canonical
        JSON; the products sorted — their queryset has no order)."""
        import hashlib
        import json

        cycle = dict(cycle_context or {})
        cycle['products'] = sorted(
            cycle.get('products') or [],
            key=lambda p: json.dumps(p, sort_keys=True, default=str),
        )
        canonical = json.dumps(
            {'cycle': cycle, 'account': account_context or {}},
            sort_keys=True, default=str,
        )
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    @staticmethod
    def latest_snapshot(dc):
        """The cycle's latest snapshot (or None) — public for the run guard."""
        return DealHealthEvidenceBuilder._latest_snapshot(dc)

    @staticmethod
    def _latest_snapshot(dc):
        from app_modules.decision_cycles.models import DealHealthSnapshot
        return (
            DealHealthSnapshot.objects
            .filter(decision_cycle=dc, client_id=dc.client_id)
            .order_by('-snapshot_date', '-created_at')
            .first()
        )

    @staticmethod
    def _parse_cursor(cursor):
        """{type: aware datetime} from a stored sources_cursor ({} / None /
        unreadable value -> that type is read in full)."""
        parsed = {}
        for key, value in (cursor or {}).items():
            moment = parse_datetime(value) if isinstance(value, str) else None
            if moment is not None:
                if timezone.is_naive(moment):
                    moment = timezone.make_aware(moment)
                parsed[key] = moment
        return parsed

    @staticmethod
    def _next_cursor(since, read_at):
        """Per type, the latest change READ now, else the previous cursor
        (nothing new of that type)."""
        cursor = {}
        for key in (DEAL_HEALTH_CURSOR_ACTIVITIES, DEAL_HEALTH_CURSOR_SIGNALS,
                    DEAL_HEALTH_CURSOR_MANAGER_NOTES):
            moment = read_at.get(key) or since.get(key)
            if moment is not None:
                cursor[key] = moment.isoformat()
        return cursor

    @staticmethod
    def _latest(moments):
        moments = [m for m in moments if m is not None]
        return max(moments) if moments else None

    # =========================================================================
    # PEOPLE NAMED TO THE LLM
    # =========================================================================

    @staticmethod
    def _validated_people_signals(dc):
        from app_modules.signals.models import PeopleSignal
        return list(
            PeopleSignal.objects.filter(
                decision_cycle=dc, status=SignalStatus.VALIDATED,
            ).select_related('target_contact', 'target_department')
        )

    @staticmethod
    def _build_roster(dc):
        return cycle_roster(dc)

    @staticmethod
    def _build_stakeholders(dc, roster):
        """Every person of the roster by label (step 5): department, role
        (read on the stakeholder's current signal) and the profile already
        known (values only — manual ones included, so the diagnostic builds
        on them). No id."""
        rows = []
        for identity, label, department in roster.entries():
            # The role + profile values: llm_people.stakeholder_prompt_facts,
            # shared with the Game Plan's roster (sprint 2, G4).
            role, profile = stakeholder_prompt_facts(stakeholder_for(dc, identity))
            rows.append({
                'ref': label,
                'department': department,
                'role': role,
                'profile': profile,
            })
        return rows

    # =========================================================================
    # CYCLE CONTEXT
    # =========================================================================

    def _build_cycle_context(self, dc):
        return self.build_cycle_context(dc, self._find_current_step(dc))

    def build_cycle_context(self, dc, current_step):
        """The deal's static context (step 3b) with ITS current step given —
        public for the Game Plan's pack (sprint 2, G7), which derives the step
        once for the whole pack."""
        from app_modules.decision_cycles.models import DealProduct

        products = (
            DealProduct.objects
            .filter(decision_cycle=dc)
            .select_related('product_catalog_entry')
        )
        campaign = dc.source_campaign if dc.source_campaign_id else None

        return {
            'id': str(dc.id),
            'name': dc.name,
            'description': dc.description or '',
            'estimated_value': str(dc.estimated_value) if dc.estimated_value else None,
            'current_step': self._serialize_step(current_step) if current_step else None,
            # The campaign the deal was born from (static context, step 3b).
            'source_campaign': (
                {
                    'type': campaign.get_campaign_type_display(),
                    'objective': campaign.activity_objective or '',
                }
                if campaign is not None else None
            ),
            'products': [
                {
                    'name': dp.product_catalog_entry.name,
                    'quantity': dp.quantity,
                    # What is sold (step 3b): read at last — never invented.
                    'description': dp.product_catalog_entry.description or '',
                    'value_proposition': dp.product_catalog_entry.value_proposition or '',
                }
                for dp in products
            ],
        }

    @staticmethod
    def _build_account_context(dc):
        return DealHealthEvidenceBuilder.account_context(dc.account)

    @staticmethod
    def account_context(account):
        """The account's static context — public for the Game Plan's pack
        (sprint 2, G7; an activity outside a cycle has an account too)."""
        return {
            'industry': (account.get_industry_display() if account.industry else None),
            'company_size': account.company_size or None,
        }

    @staticmethod
    def _find_current_step(dc):
        """The cycle's current step, derived ONCE for the whole cycle
        (decision_steps_state — the shared definition of
        DecisionStep.is_current) instead of one is_current per step, each
        re-deriving the cycle. Sprint « Deal health v2 », step 2."""
        from app_modules.activities.services.next_step_materialization import (
            current_decision_step,
        )
        return current_decision_step(dc)

    @staticmethod
    def _serialize_step(step):
        return {
            # The PipelineStep value — persisted as the snapshot's
            # declared_step (not rendered in the prompt).
            'stage': step.stage,
            'name': step.name,
            'goal': step.goal or '',
            'criterias': step.criterias or [],
            'metrics': step.metrics or [],
        }

    # =========================================================================
    # PEOPLE
    # =========================================================================

    def _build_people(self, dc, roster):
        result = PeopleConsolidationService().consolidate(dc)
        signals = {str(s.id): s for s in self._validated_people_signals(dc)}
        qualified = []
        for entry in result['qualified']:
            # UNKNOWN is kept (TD-279 U) and shown as a role to qualify.
            if entry['role'] == PeopleRole.UNKNOWN:
                entry['role_display'] = PEOPLE_ROLE_TO_QUALIFY
            # The consolidation (shared with the UI) carries the contact's
            # full identity: the PACK keeps only the llm_people label.
            signal = signals.get(entry['signal_id'])
            safe = {k: v for k, v in entry.items() if k not in ('target_contact', 'full_name')}
            safe['name'] = roster.label(signal) if signal is not None else ''
            qualified.append(safe)
        return {
            'qualified': qualified,
            'unqualified_count': len(result['unqualified']),
        }

    # =========================================================================
    # SIGNALS — grouped by type, VALIDATED only
    # =========================================================================

    def _build_signals(self, dc, roster, since=None):
        """The validated signals changed after `since` (all when None), and
        the latest updated_at read (None when none)."""
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

        def fresh(model):
            return self.fresh_signals_qs(model, dc, since)

        # Sub-step 4 recabling: the competitor facet is sourced from the
        # detached CompetitorSignal (DC-scoped + VALIDATED), not from
        # TechStackSignal.is_competitor. We match a tech row to a competitor
        # by its normalised name (the backfill mirrors every is_competitor
        # techstack into a CompetitorSignal with the same normalised name, so
        # the marker stays strictly equivalent). Output shape is unchanged.
        competitor_norms = set(
            CompetitorSignal.objects.filter(
                decision_cycle=dc, status=validated,
            ).values_list('competitor_name_normalized', flat=True)
        )

        rows = {
            'pain': self._serialize_pain_signals(
                fresh(PainSignal).prefetch_related('target_departments')
            ),
            'objective': self._serialize_objective_signals(
                fresh(ObjectiveSignal).select_related('target_department', 'target_contact')
            ),
            'impact': self._serialize_impact_signals(
                fresh(ImpactSignal).prefetch_related('target_departments')
            ),
            # S10: tech identity lives on the signal's own columns, so
            # the catalogue FK is no longer joined.
            'techstack': self._serialize_techstack_signals(
                fresh(TechStackSignal).prefetch_related('usage_departments'),
                competitor_norms,
            ),
            'blocker': self._serialize_blocker_signals(
                fresh(BlockerSignal).select_related('contact'),
                roster,
            ),
            'constraint': self._serialize_constraint_signals(
                fresh(ConstraintSignal).prefetch_related('target_departments')
            ),
            'people': self._serialize_people_signals(
                fresh(PeopleSignal).select_related('target_contact', 'target_department'),
                roster,
            ),
            # Read DIRECTLY (step 3b), not only through a tech row.
            'competitor': self._serialize_competitor_signals(fresh(CompetitorSignal)),
        }
        latest = self._latest(
            fresh(model).aggregate(latest=Max('updated_at'))['latest']
            for model in self.signal_models()
        )
        return rows, latest

    # -- Per-type serializers --

    @staticmethod
    def _serialize_pain_signals(qs):
        return [
            {
                'summary': s.summary,
                'source_quote': s.source_quote or '',
                'canonical_key': s.canonical_key,
                # Multi-department scope (sub-step 2b): list of concerned
                # departments read off the target_departments M2M. Consumed by
                # diagnostic_v1._format_signal (which already renders the list).
                'target_departments': [
                    d.get_name_display() for d in s.target_departments.all()
                ],
                'scope_level': s.scope_level,
                'what': s.what,
                'dimension': s.dimension,
            }
            for s in qs
        ]

    @staticmethod
    def serialize_objective_signals(qs):
        """The Objective rows of the AI packs — public for the Game Plan's
        pack (sprint 2, G7), which reuses them as they are."""
        return DealHealthEvidenceBuilder._serialize_objective_signals(qs)

    @staticmethod
    def _serialize_objective_signals(qs):
        return [
            {
                'summary': s.summary,
                'source_quote': s.source_quote or '',
                'canonical_key': s.canonical_key,
                'target_department': (
                    s.target_department.get_name_display()
                    if s.target_department else None
                ),
                'scope_level': s.scope_level,
                'what': s.what,
                'dimension': s.dimension,
                # A14: read when entered (the extraction emits them at
                # sprint 2).
                'success_criteria': s.success_criteria or '',
                'target_date': s.target_date.isoformat() if s.target_date else '',
                'notes': s.notes or '',
            }
            for s in qs
        ]

    @staticmethod
    def _serialize_impact_signals(qs):
        return [
            {
                'summary': s.summary,
                'source_quote': s.source_quote or '',
                'canonical_key': s.canonical_key,
                # Multi-department scope (sub-step 2b): list of concerned
                # departments read off the target_departments M2M.
                'target_departments': [
                    d.get_name_display() for d in s.target_departments.all()
                ],
                'scope_level': s.scope_level,
                'what': s.what,
                'dimension': s.dimension,
                'impact_type': s.impact_type,
                'metric_text': s.metric_text or '',
                'human_impact': s.human_impact or '',
            }
            for s in qs
        ]

    @staticmethod
    def serialize_techstack_signals(qs, competitor_norms=frozenset()):
        """The TechStack rows of the AI packs (step 3b, TD-314) — public for
        the prep-call / Game Plan pack (sprint 2, S6), which reuses them as
        they are. `qs` should prefetch `usage_departments`."""
        return DealHealthEvidenceBuilder._serialize_techstack_signals(qs, competitor_norms)

    @staticmethod
    def _serialize_techstack_signals(qs, competitor_norms=frozenset()):
        """
        Tech evidence, read entirely off the signal (S10).

        Sub-step 4: `is_competitor` is no longer read off the tech row's own
        flag — it now reflects whether a detached CompetitorSignal (DC-scoped
        + VALIDATED) names this tool, matched on the normalised name via
        `competitor_norms`. The emitted key and the downstream "Competitor:
        yes" rendering are unchanged.

        Was: the tool label came from str(tech_catalog_entry) and the two
        commercial flags from that catalogue row. The extractor no longer
        populates the FK, so all three emitted None / False / False and
        the tool name vanished from the diagnostic prompt.

        `canonical_key` is not emitted: TechStack is not clusterable, so
        it was always None. diagnostic_v1._format_signal falls back to the
        signal type for its header line when the key is absent.

        `is_to_replace` is no longer read (step 3b): the extraction always
        writes False since the TechStack sprint.

        TD-314 (step 3b): the usage scope (DEPARTMENT / COMPANY / UNKNOWN)
        and the discontinuation — a past date = no longer used, a future
        date = a planned exit (TechStackSignal.discontinued_date help text).

        `is_integration` is no longer emitted (sub-step 9b): the manual tag was
        retired and an integration requirement now surfaces via the TECHNICAL
        ConstraintSignal path, not off the tech row.
        """
        today = timezone.localdate()
        return [
            {
                'summary': '',
                'source_quote': s.source_quote or '',
                'tech_name': s.tech_name or '',
                'is_competitor': s.tech_name_normalized in competitor_norms,
                'on_deal': s.decision_cycle_id is not None,
                'usage_scope': s.get_usage_scope_display() if s.usage_scope else None,
                'discontinued': (
                    None if not s.is_discontinued
                    else TECHSTACK_NO_LONGER_USED
                    if (s.discontinued_date is None or s.discontinued_date <= today)
                    else TECHSTACK_PLANNED_EXIT
                ),
                'discontinued_date': (
                    s.discontinued_date.isoformat() if s.is_discontinued and s.discontinued_date else ''
                ),
                # WHO uses the tool -- multi-department. The list reflects
                # every designated using department ([] when none). Replaces
                # the legacy single usage_department string (mono -> multi).
                'usage_departments': [
                    d.get_name_display() for d in s.usage_departments.all()
                ],
            }
            for s in qs
        ]

    @staticmethod
    def _serialize_blocker_signals(qs, roster):
        return [
            {
                'summary': s.summary,
                'source_quote': s.source_quote or '',
                'canonical_key': s.canonical_key,
                # llm_people label (first name only).
                'contact_name': roster.label(s.contact) if s.contact else None,
            }
            for s in qs
        ]

    @staticmethod
    def _serialize_constraint_signals(qs):
        # Constraints are detached from the what × dimension canonical axes:
        # canonical_key is always None and what/dimension are legacy. The
        # deal-health prompt consumes only summary + rigidity, so the payload
        # carries the classification axis (nature) and scope instead.
        return [
            {
                'summary': s.summary,
                'source_quote': s.source_quote or '',
                'nature': s.nature,
                # Multi-department scope (sub-step 1b): the list of concerned
                # departments read off the target_departments M2M (a mono-
                # department constraint yields a 1-element list). Replaces the
                # single target_department FK string.
                'target_departments': [
                    d.get_name_display() for d in s.target_departments.all()
                ],
                'rigidity': s.rigidity,
            }
            for s in qs
        ]

    @staticmethod
    def _serialize_people_signals(qs, roster):
        return [
            {
                'summary': '',
                'source_quote': s.source_quote or '',
                'canonical_key': s.canonical_key,
                'role': people_role_for_prompt(s.role),
                'influence': s.influence or '',
                'target_department': (
                    s.target_department.get_name_display()
                    if s.target_department else None
                ),
                # llm_people label (first name only).
                'target_contact': roster.label(s) if s.target_contact else None,
                'notes': s.notes or '',
            }
            for s in qs
        ]

    @staticmethod
    def _serialize_competitor_signals(qs):
        return [
            {
                'summary': s.summary or '',
                'source_quote': s.source_quote or '',
                'competitor_name': s.competitor_name or '',
            }
            for s in qs
        ]

    # =========================================================================
    # ACTIVITIES (step 3b, amendment A2)
    # =========================================================================

    # The activity fields read — an activity is new evidence when one of them
    # is filled and the activity changed after the cursor (analysed or not).
    _ACTIVITY_TEXT_FIELDS = (
        'transcript', 'outcome_notes', 'description', 'call_to_action', 'outcome',
    )

    def _build_activities(self, dc, since=None):
        """The activities of the cycle changed after `since` (all when None)
        and carrying content, OLDEST first; and the latest updated_at read."""
        qs = self.fresh_activities_qs(dc, since).select_related('decision_step')
        activities = sorted(qs, key=self._activity_moment)
        rows = [
            {
                'activity_id': str(a.id),
                'type': a.activity_type,
                'status': a.status,
                'date': self._activity_moment(a).date().isoformat(),
                'step': a.decision_step.name if a.decision_step_id else None,
                'objective': a.call_to_action or '',
                'description': a.description or '',
                'outcome': a.get_outcome_display() if a.outcome else '',
                'notes': a.outcome_notes or '',
                # Call / meeting transcript, or the email content (PO: an
                # email's content is Activity.transcript).
                'transcript': a.transcript or '',
            }
            for a in activities
        ]
        return rows, self._latest(a.updated_at for a in activities)

    @staticmethod
    def _activity_moment(activity):
        """When the activity happened: completed, else scheduled, else
        created — the order of « oldest first »."""
        from datetime import datetime, time
        if activity.completed_at:
            return activity.completed_at
        if activity.scheduled_date:
            return timezone.make_aware(datetime.combine(activity.scheduled_date, time.min))
        return activity.created_at

    # =========================================================================
    # MANAGER NOTES (step 3b)
    # =========================================================================

    @staticmethod
    def manager_notes(dc):
        """Every ManagerNote of the cycle, as the deal health reads them —
        public for the Game Plan's pack (sprint 2, G7)."""
        return DealHealthEvidenceBuilder._build_manager_notes(dc)[0]

    @staticmethod
    def activity_moment(activity):
        """Public for the Game Plan's pack (G7): when the activity happened."""
        return DealHealthEvidenceBuilder._activity_moment(activity)

    @staticmethod
    def _build_manager_notes(dc, since=None):
        """The ManagerNotes created after `since` (all when None), oldest
        first, the author named by the ROLE only; and the latest created_at."""
        qs = (
            DealHealthEvidenceBuilder.fresh_manager_notes_qs(dc, since)
            .select_related('created_by__role')
            .order_by('created_at', 'id')
        )
        notes = list(qs)
        rows = [
            {
                'date': n.created_at.date().isoformat(),
                'author_role': DealHealthEvidenceBuilder._note_author_role(n.created_by),
                'content': n.content,
            }
            for n in notes
        ]
        return rows, DealHealthEvidenceBuilder._latest(n.created_at for n in notes)

    @staticmethod
    def _note_author_role(user):
        # Only managers and admins write notes (manager_note_views.py);
        # read off the role flags, never the name.
        if user is not None and user.has_admin_rights():
            return DEAL_HEALTH_NOTE_AUTHOR_ADMIN
        return DEAL_HEALTH_NOTE_AUTHOR_MANAGER

    # =========================================================================
    # INPUT BOUNDS (amendment A3)
    # =========================================================================

    def _apply_input_bounds(self, activities, signals, notes):
        """
        Cut the transcripts so the source texts fit the bounds — IN PLACE on
        `activities` (oldest first). Validated signals and notes always pass
        whole. Returns the trace (None when nothing was cut).

          1. a transcript above MAX_CHARS_PER_SOURCE is cut to it;
          2. above MAX_INPUT_CHARS in total, the OLDEST transcripts are cut
             first, as much as needed (possibly to nothing).
        """
        cuts = []

        def cut(row, keep, reason):
            text = row['transcript']
            original = row.get('_original_chars', len(text))
            row['_original_chars'] = original
            row['transcript'] = (
                text[:keep] + '\n' + DEAL_HEALTH_TRUNCATION_MARKER.format(kept=keep, total=original)
            )
            row['_kept_chars'] = keep
            cuts.append({'activity_id': row['activity_id'], 'date': row['date'],
                         'type': row['type'], 'reason': reason,
                         'original_chars': original, 'kept_chars': keep})

        for row in activities:
            if len(row['transcript']) > self.MAX_CHARS_PER_SOURCE:
                cut(row, self.MAX_CHARS_PER_SOURCE, DEAL_HEALTH_TRUNCATION_PER_SOURCE)

        def transcript_chars(row):
            return row.get('_kept_chars', len(row['transcript']))

        other_chars = sum(
            len(str(value)) for row in activities
            for key, value in row.items() if key not in ('transcript', 'activity_id') and not key.startswith('_')
        ) + sum(
            len(str(value)) for rows in signals.values() for row in rows for value in row.values()
            if isinstance(value, str)
        ) + sum(len(n['content']) for n in notes)
        total_before = other_chars + sum(len(r['transcript']) for r in activities)
        overflow = other_chars + sum(transcript_chars(r) for r in activities) - self.MAX_INPUT_CHARS

        for row in activities:                       # oldest first
            if overflow <= 0:
                break
            current = transcript_chars(row)
            if current == 0:
                continue
            keep = max(0, current - overflow)
            overflow -= current - keep
            cut(row, keep, DEAL_HEALTH_TRUNCATION_INPUT_BUDGET)

        for row in activities:
            row.pop('_original_chars', None)
            row.pop('_kept_chars', None)
        if not cuts:
            return None
        return {
            'max_chars_per_source': self.MAX_CHARS_PER_SOURCE,
            'max_input_chars': self.MAX_INPUT_CHARS,
            'source_chars_before': total_before,
            'over_budget_chars': max(0, overflow),
            'cuts': cuts,
        }

    # =========================================================================
    # PREVIOUS SNAPSHOT
    # =========================================================================

    @staticmethod
    def _build_previous_snapshot(snapshot):
        """The previous diagnostic: its FULL JSON when v2, its
        global_reading when v1 (step 3b)."""
        if not snapshot:
            return None

        diagnostic = snapshot.diagnostic or {}
        return {
            'schema_version': snapshot.schema_version,
            'global_reading': diagnostic.get('global_reading', ''),
            'diagnostic': (
                diagnostic if snapshot.schema_version == DEAL_HEALTH_SCHEMA_V2 else None
            ),
            'snapshot_date': (
                snapshot.snapshot_date.isoformat()
                if snapshot.snapshot_date else ''
            ),
        }
