# backend/tests/ai_pipelines/deal_health_fixtures.py
"""
Shared deal-health answers for the tests (sprint « Deal health v2 »).

V1_DIAGNOSTIC — the original diagnostic (7 dimensions, gaps, levers,
themes); the shape DealHealthView and the prep call read.
V2_DIAGNOSTIC — the « manager / coach » answer (step 5): every V1 key kept
as is (amendment A5) + the v2 keys; no stakeholder entry (tests that need
profiles add their own).
"""

import copy

V1_DIAGNOSTIC = {
    'global_reading': 'The client recognizes an operational problem.',
    'dimensions': [
        {'key': 'problem_recognized', 'status': 'confirmed', 'evidence': 'Quote A', 'missing': ''},
        {'key': 'felt_pain', 'status': 'missing_evidence', 'evidence': '', 'missing': 'Not explored'},
        {'key': 'impact_understood', 'status': 'unclear', 'evidence': 'Partial', 'missing': 'Quantification'},
        {'key': 'desired_gain', 'status': 'suggested', 'evidence': 'Mentioned goal', 'missing': ''},
        {'key': 'urgency', 'status': 'missing_evidence', 'evidence': '', 'missing': 'No timeline'},
        {'key': 'willingness_to_act', 'status': 'unclear', 'evidence': '', 'missing': 'Budget unclear'},
        {'key': 'solution_trust', 'status': 'suggested', 'evidence': 'Positive demo', 'missing': ''},
    ],
    'discovery_gaps': [
        {
            'kind': 'qualification',
            'dimension': 'felt_pain',
            'public_text': 'Pain depth not yet qualified.',
            'suggested_questions': ['How does this impact your daily work?'],
        },
    ],
    'levers': {
        'desires': [{'summary': 'Better reporting', 'theme': 'OPS:TIME'}],
        'value': [{'summary': '10h/week recoverable', 'theme': 'OPS:TIME'}],
        'cost': [{'summary': 'Budget not owned by champion'}],
        'constraints': [{'summary': 'ROI > 20%', 'rigidity': 'FIRM', 'is_metric': True}],
    },
    'themes': [{'label': 'Ops efficiency', 'summary': 'Pain recognized.'}],
    'evidence_scope': {'validated_signals_count': 5, 'note': 'Based on captured evidence.'},
}

_V2_KEYS = {
    'summary': 'An operational problem is recognised; budget and timeline are unknown.',
    'needs_and_urgency': {
        'status': 'suggested', 'assessment': 'Need recognised, urgency not proven.',
        'cost_of_inaction': 'Unknown',
    },
    'credibility': {'status': 'unclear', 'assessment': 'No proof shared yet.'},
    'fit_and_value': {
        'status': 'missing_evidence', 'assessment': 'Requirements not documented.',
        'requirements': [], 'competitive_position': 'Unknown',
    },
    'buying_process': {'assessment': 'Unknown', 'steps': [], 'timeline': 'Unknown'},
    'bant': {
        'budget': {'status': 'unknown', 'reason': 'Not discussed.'},
        'authority': {'status': 'unknown', 'reason': 'Not discussed.'},
        'need': {'status': 'validated', 'reason': 'Problem recognised.'},
        'timeline': {'status': 'unknown', 'reason': 'Not discussed.'},
    },
    'strategic_conclusion': 'Qualify budget and timeline at the next meeting.',
    'levers_to_invest': [],
    'objectives': {'deal': 'Unknown', 'next_activity': ['Qualify the budget']},
    'missing_info': [],
    'estimated_step': {'step': 'QUALIFICATION', 'reason': 'BANT not validated yet.'},
    'top_arguments': [],
    'stakeholders': [],
}

V2_DIAGNOSTIC = {**copy.deepcopy(V1_DIAGNOSTIC), **copy.deepcopy(_V2_KEYS)}
