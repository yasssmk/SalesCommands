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

from app_modules.signals.constants import SignalStatus

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

        return {
            'cycle': self._build_cycle_context(dc),
            'readiness': ReadinessScoreService().calculate(dc),
            'people': self._build_people(dc),
            'signals': self._build_signals(dc),
            'previous_snapshot': self._build_previous_snapshot(dc),
        }

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
        steps = dc.steps.select_related('previous_step').order_by('order')
        for step in steps:
            if step.is_current:
                return step
        return None

    @staticmethod
    def _serialize_step(step):
        return {
            'name': step.name,
            'goal': step.goal or '',
            'criterias': step.criterias or [],
            'metrics': step.metrics or [],
        }

    # =========================================================================
    # PEOPLE
    # =========================================================================

    @staticmethod
    def _build_people(dc):
        result = PeopleConsolidationService().consolidate(dc)
        return {
            'qualified': result['qualified'],
            'unqualified_count': len(result['unqualified']),
        }

    # =========================================================================
    # SIGNALS — grouped by type, VALIDATED only
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
            'pain': self._serialize_pain_signals(
                PainSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).select_related('target_department')
            ),
            'objective': self._serialize_objective_signals(
                ObjectiveSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).select_related('target_department', 'target_contact')
            ),
            'impact': self._serialize_impact_signals(
                ImpactSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).select_related('target_department')
            ),
            'techstack': self._serialize_techstack_signals(
                TechStackSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).select_related('tech_catalog_entry', 'usage_department')
            ),
            'blocker': self._serialize_blocker_signals(
                BlockerSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).select_related('contact')
            ),
            'constraint': self._serialize_constraint_signals(
                ConstraintSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).select_related('target_department')
            ),
            'people': self._serialize_people_signals(
                PeopleSignal.objects.filter(
                    decision_cycle=dc, status=validated,
                ).select_related('target_contact', 'target_department')
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
                'target_department': (
                    s.target_department.get_name_display()
                    if s.target_department else None
                ),
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
    def _serialize_techstack_signals(qs):
        return [
            {
                'summary': '',
                'source_quote': s.source_quote or '',
                'canonical_key': s.canonical_key,
                'catalog_name': (
                    str(s.tech_catalog_entry)
                    if s.tech_catalog_entry else None
                ),
                'is_competitor': (
                    s.tech_catalog_entry.is_competitor
                    if s.tech_catalog_entry else False
                ),
                'is_integration_target': (
                    s.tech_catalog_entry.is_integration_target
                    if s.tech_catalog_entry else False
                ),
                'on_deal': s.decision_cycle_id is not None,
                'usage_department': (
                    s.usage_department.get_name_display()
                    if s.usage_department else None
                ),
            }
            for s in qs
        ]

    @staticmethod
    def _serialize_blocker_signals(qs):
        return [
            {
                'summary': s.summary,
                'source_quote': s.source_quote or '',
                'canonical_key': s.canonical_key,
                'contact_name': (
                    f"{s.contact.first_name} {s.contact.last_name}".strip()
                    if s.contact else None
                ),
            }
            for s in qs
        ]

    @staticmethod
    def _serialize_constraint_signals(qs):
        return [
            {
                'summary': s.summary,
                'source_quote': s.source_quote or '',
                'canonical_key': s.canonical_key,
                'target_department': (
                    s.target_department.get_name_display()
                    if s.target_department else None
                ),
                'rigidity': s.rigidity,
                'what': s.what,
                'dimension': s.dimension,
            }
            for s in qs
        ]

    @staticmethod
    def _serialize_people_signals(qs):
        return [
            {
                'summary': '',
                'source_quote': s.source_quote or '',
                'canonical_key': s.canonical_key,
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
