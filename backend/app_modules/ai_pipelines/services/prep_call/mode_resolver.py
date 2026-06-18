# app_modules/ai_pipelines/services/prep_call/mode_resolver.py
"""
Deterministic brief-mode resolver for the prep-call pipeline.

Evaluates the maturity snapshot dimensions and returns one of the four
brief modes (DISCOVERY, CONVICTION, PROOF, DECISION). Called BEFORE
the LLM — no AI involved.

Rules source: guide/To_IMPLEMENT/step3_Copilote.md §5.0
"""

from app_modules.ai_pipelines.services.prep_call.rhetoric_guide import (
    BRIEF_MODES,
)

MATURITY_DIMENSIONS = (
    'problem_recognized',
    'felt_pain',
    'impact_understood',
    'desired_gain',
    'urgency',
    'willingness_to_act',
    'solution_trust',
)

_WEAK = frozenset(('missing_evidence', 'unclear'))
_WEAK_OR_CONTRADICTORY = frozenset(('missing_evidence', 'unclear', 'contradictory'))
_STRONG = frozenset(('confirmed', 'suggested'))


def resolve_brief_mode(maturity_snapshot):
    """
    Resolve the brief mode from a maturity snapshot dict.

    Args:
        maturity_snapshot: dict with a ``dimensions`` list of
            ``{"key": str, "status": str}`` entries, or None.

    Returns:
        One of ``'DISCOVERY'``, ``'CONVICTION'``, ``'PROOF'``,
        ``'DECISION'``.
    """
    if maturity_snapshot is None:
        return 'DISCOVERY'

    dims = _extract_dimensions(maturity_snapshot)
    if not dims:
        return 'DISCOVERY'

    weak_count = sum(1 for s in dims.values() if s in _WEAK)
    strong_count = sum(1 for s in dims.values() if s in _STRONG)

    # Rule 3: majority weak → DISCOVERY
    if weak_count > len(dims) / 2:
        return 'DISCOVERY'

    # Rule 4: problem recognized but pain/urgency still weak → CONVICTION
    if (
        dims.get('problem_recognized') == 'confirmed'
        and (
            dims.get('felt_pain') in _WEAK
            or dims.get('urgency') in _WEAK
        )
    ):
        return 'CONVICTION'

    # Rule 5: good conviction (4+ strong) but solution_trust weak → PROOF
    if (
        strong_count >= 4
        and dims.get('solution_trust') in _WEAK_OR_CONTRADICTORY
    ):
        return 'PROOF'

    # Rule 6: high maturity including solution_trust confirmed → DECISION
    if (
        strong_count > len(dims) / 2
        and dims.get('solution_trust') == 'confirmed'
    ):
        return 'DECISION'

    # Rule 7: safe fallback
    return 'DISCOVERY'


def _extract_dimensions(maturity_snapshot):
    """
    Parse the dimensions list into a {key: status} dict.

    Only known dimension keys are retained.
    """
    raw = maturity_snapshot.get('dimensions') or []
    return {
        d['key']: d['status']
        for d in raw
        if d.get('key') in MATURITY_DIMENSIONS and d.get('status')
    }
