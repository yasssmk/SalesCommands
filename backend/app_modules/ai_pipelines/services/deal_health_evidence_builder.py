# app_modules/ai_pipelines/services/deal_health_evidence_builder.py
"""
DealHealthEvidenceBuilder — assembles the deterministic evidence pack
consumed by the deal-health pipeline prompts.

Stateless, read-only, no LLM. Queries validated signals by type,
readiness score, people consolidation, cycle context (step, products),
and the previous snapshot.

The pack shape is the contract between this builder, the context layer,
and the diagnostic request layer.
"""

import logging

from app_modules.ai_pipelines.constants import (
    PEOPLE_ROLE_TO_QUALIFY,
    people_role_for_prompt,
)
from app_modules.ai_pipelines.services.llm_people import cycle_roster
from app_modules.signals.constants import PeopleRole, SignalStatus

from app_modules.decision_cycles.services.readiness_score_service import (
    ReadinessScoreService,
)
from app_modules.decision_cycles.services.people_consolidation_service import (
    PeopleConsolidationService,
)


logger = logging.getLogger(__name__)


class DealHealthEvidenceBuilder:
    """
    Assembles the evidence pack for a DecisionCycle.

    Usage:
        pack = DealHealthEvidenceBuilder().build(decision_cycle)
    """

    def build(self, decision_cycle):
        """
        Build the evidence pack dict.

        Args:
            decision_cycle: DecisionCycle instance.

        Returns:
            dict with keys: cycle, readiness, people, signals,
            previous_snapshot.
        """
        dc = decision_cycle
        # ONE roster for the whole prompt: every person is named by
        # llm_people (first name only, homonyms told apart — sprint « Deal
        # health v2 », step 3a), the same label wherever they appear.
        roster = self._build_roster(dc)

        return {
            'cycle': self._build_cycle_context(dc),
            'readiness': ReadinessScoreService().calculate(dc),
            'people': self._build_people(dc, roster),
            'signals': self._build_signals(dc, roster),
            'previous_snapshot': self._build_previous_snapshot(dc),
        }

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

    # =========================================================================
    # CYCLE CONTEXT
    # =========================================================================

    def _build_cycle_context(self, dc):
        from app_modules.decision_cycles.models import DealProduct

        current_step = self._find_current_step(dc)
        products = (
            DealProduct.objects
            .filter(decision_cycle=dc)
            .select_related('product_catalog_entry')
        )

        return {
            'id': str(dc.id),
            'name': dc.name,
            'estimated_value': str(dc.estimated_value) if dc.estimated_value else None,
            'current_step': self._serialize_step(current_step) if current_step else None,
            'products': [
                {
                    'name': dp.product_catalog_entry.name,
                    'quantity': dp.quantity,
                }
                for dp in products
            ],
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

    def _build_signals(self, dc, roster):
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

        return {
            'pain': self._serialize_pain_signals(
                PainSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).prefetch_related('target_departments')
            ),
            'objective': self._serialize_objective_signals(
                ObjectiveSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).select_related('target_department', 'target_contact')
            ),
            'impact': self._serialize_impact_signals(
                ImpactSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).prefetch_related('target_departments')
            ),
            # S10: tech identity lives on the signal's own columns, so
            # the catalogue FK is no longer joined.
            'techstack': self._serialize_techstack_signals(
                TechStackSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).prefetch_related('usage_departments'),
                competitor_norms,
            ),
            'blocker': self._serialize_blocker_signals(
                BlockerSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).select_related('contact'),
                roster,
            ),
            'constraint': self._serialize_constraint_signals(
                ConstraintSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).prefetch_related('target_departments')
            ),
            'people': self._serialize_people_signals(
                PeopleSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).select_related('target_contact', 'target_department'),
                roster,
            ),
        }

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

        `is_to_replace` is new here — the catalogue had no equivalent.

        `is_integration` is no longer emitted (sub-step 9b): the manual tag was
        retired and an integration requirement now surfaces via the TECHNICAL
        ConstraintSignal path, not off the tech row.
        """
        return [
            {
                'summary': '',
                'source_quote': s.source_quote or '',
                'tech_name': s.tech_name or '',
                'is_competitor': s.tech_name_normalized in competitor_norms,
                'is_to_replace': s.is_to_replace,
                'on_deal': s.decision_cycle_id is not None,
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

    # =========================================================================
    # PREVIOUS SNAPSHOT
    # =========================================================================

    @staticmethod
    def _build_previous_snapshot(dc):
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
            'snapshot_date': (
                snapshot.snapshot_date.isoformat()
                if snapshot.snapshot_date else ''
            ),
        }
