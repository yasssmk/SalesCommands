# tests/ai_pipelines/test_prep_call_mode_resolver.py
"""
Tests for resolve_brief_mode() — pure Python, no DB, no Django.

Covers all 7 rules from spec §5.0 v1.1.
"""

from app_modules.ai_pipelines.services.prep_call.mode_resolver import (
    resolve_brief_mode,
)


def _snapshot(dims):
    """Build a maturity snapshot dict from a {key: status} mapping."""
    return {
        'dimensions': [
            {'key': k, 'status': v} for k, v in dims.items()
        ],
    }


_ALL_DIMS = (
    'problem_recognized',
    'felt_pain',
    'impact_understood',
    'desired_gain',
    'urgency',
    'willingness_to_act',
    'solution_trust',
)


def test_none_returns_discovery():
    assert resolve_brief_mode(None) == 'DISCOVERY'


def test_empty_dict_returns_discovery():
    assert resolve_brief_mode({}) == 'DISCOVERY'


def test_no_dimensions_key_returns_discovery():
    assert resolve_brief_mode({'global_reading': 'some text'}) == 'DISCOVERY'


def test_majority_missing_evidence_returns_discovery():
    dims = {d: 'missing_evidence' for d in _ALL_DIMS}
    dims['problem_recognized'] = 'confirmed'
    dims['desired_gain'] = 'suggested'
    assert resolve_brief_mode(_snapshot(dims)) == 'DISCOVERY'


def test_problem_recognized_but_pain_weak_returns_conviction():
    dims = {
        'problem_recognized': 'confirmed',
        'felt_pain': 'missing_evidence',
        'impact_understood': 'suggested',
        'desired_gain': 'confirmed',
        'urgency': 'confirmed',
        'willingness_to_act': 'suggested',
        'solution_trust': 'suggested',
    }
    assert resolve_brief_mode(_snapshot(dims)) == 'CONVICTION'


def test_problem_recognized_but_urgency_weak_returns_conviction():
    dims = {
        'problem_recognized': 'confirmed',
        'felt_pain': 'confirmed',
        'impact_understood': 'suggested',
        'desired_gain': 'confirmed',
        'urgency': 'unclear',
        'willingness_to_act': 'suggested',
        'solution_trust': 'suggested',
    }
    assert resolve_brief_mode(_snapshot(dims)) == 'CONVICTION'


def test_conviction_present_but_solution_trust_weak_returns_proof():
    dims = {
        'problem_recognized': 'confirmed',
        'felt_pain': 'confirmed',
        'impact_understood': 'suggested',
        'desired_gain': 'confirmed',
        'urgency': 'confirmed',
        'willingness_to_act': 'suggested',
        'solution_trust': 'unclear',
    }
    assert resolve_brief_mode(_snapshot(dims)) == 'PROOF'


def test_solution_trust_contradictory_returns_proof():
    dims = {
        'problem_recognized': 'confirmed',
        'felt_pain': 'confirmed',
        'impact_understood': 'suggested',
        'desired_gain': 'confirmed',
        'urgency': 'confirmed',
        'willingness_to_act': 'suggested',
        'solution_trust': 'contradictory',
    }
    assert resolve_brief_mode(_snapshot(dims)) == 'PROOF'


def test_majority_strong_and_solution_trust_confirmed_returns_decision():
    dims = {
        'problem_recognized': 'confirmed',
        'felt_pain': 'confirmed',
        'impact_understood': 'confirmed',
        'desired_gain': 'confirmed',
        'urgency': 'confirmed',
        'willingness_to_act': 'suggested',
        'solution_trust': 'confirmed',
    }
    assert resolve_brief_mode(_snapshot(dims)) == 'DECISION'


def test_fallback_returns_discovery():
    dims = {
        'problem_recognized': 'unclear',
        'felt_pain': 'suggested',
        'impact_understood': 'unclear',
        'desired_gain': 'suggested',
        'urgency': 'suggested',
        'willingness_to_act': 'unclear',
        'solution_trust': 'suggested',
    }
    assert resolve_brief_mode(_snapshot(dims)) == 'DISCOVERY'
