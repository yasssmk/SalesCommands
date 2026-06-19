# app_modules/ai_pipelines/services/prep_call/rhetoric_guide.py
"""
Rhetoric guide constants for the prep-call pipeline.

Pure data — no logic, no functions. Consumed by:
  - mode_resolver.py (brief mode selection rules)
  - prompts/prep_call/ (injected into LLM prompt as structured context)

Source of truth: guide/To_IMPLEMENT/step3_Copilote.md §5.0–§5.4
"""


# =============================================================================
# BRIEF MODES (§5.0)
# =============================================================================

BRIEF_MODES = {
    'DISCOVERY': {
        'description': 'Insufficient evidence — major gaps remain.',
        'trigger': (
            'Evidence is sparse: pain or urgency unproven, stakeholder '
            'map unclear, or most maturity dimensions show '
            'missing_evidence / unclear.'
        ),
        'priority': (
            'Surface information: discovery questions, identify who to '
            'address. No premature argumentation.'
        ),
    },
    'CONVICTION': {
        'description': 'Problem acknowledged but not yet a priority.',
        'trigger': (
            'Problem is recognized (confirmed/suggested) but felt_pain, '
            'urgency, or impact_understood remain unclear or '
            'missing_evidence.'
        ),
        'priority': (
            'Turn interest into a business stake: connect to business '
            'outcomes, make the cost of inaction tangible.'
        ),
    },
    'PROOF': {
        'description': 'Conviction present but solution trust is weak.',
        'trigger': (
            'Most buying-maturity dimensions are confirmed or suggested, '
            'but solution_trust is unclear or missing_evidence.'
        ),
        'priority': (
            'Demonstrate: concrete use case, quantified ROI, lift doubt '
            'through proof.'
        ),
    },
    'DECISION': {
        'description': 'High maturity — time to engage.',
        'trigger': (
            'Majority of dimensions confirmed or suggested, including '
            'solution_trust. The deal is mature enough to push for '
            'commitment.'
        ),
        'priority': (
            'Secure commitment: firm next step, contrast inaction vs '
            'action, schedule a dated meeting.'
        ),
    },
}


# =============================================================================
# RHETORIC REGISTERS (§5.1)
# =============================================================================

RHETORIC_REGISTERS = {
    'DEMONSTRATIVE': {
        'name': 'Demonstrative (logos)',
        'purpose': 'Convince through logic and facts.',
        'procedures': (
            'Three-step reasoning, causality chains, hard numbers.'
        ),
        'when_to_use': (
            'Analytical profiles (CFO, IT, investor); demonstrating ROI.'
        ),
        'avoid_if': 'The audience wants to be inspired, not calculated at.',
    },
    'NARRATIVE': {
        'name': 'Narrative (pathos)',
        'purpose': 'Make the audience feel and identify with the problem.',
        'procedures': (
            'Lived experience, frustration-to-relief contrast.'
        ),
        'when_to_use': (
            'Field audience (users, champion); making the pain real.'
        ),
        'avoid_if': 'The audience expects concrete data, not stories.',
    },
    'EPIDEICTIC': {
        'name': 'Epideictic (valorization)',
        'purpose': 'Magnify a vision or transformation.',
        'procedures': 'Glorification of progress and mastery.',
        'when_to_use': 'Cycle closure, vision-selling moments.',
        'avoid_if': 'Grandiloquent without proof to back it up.',
    },
    'DELIBERATIVE': {
        'name': 'Deliberative (action)',
        'purpose': 'Push toward a decision.',
        'procedures': (
            'Call to action, antithesis "endure vs. steer".'
        ),
        'when_to_use': 'Closing, end of call, decision-makers.',
        'avoid_if': 'The audience is not yet convinced.',
    },
    'ANALOGICAL': {
        'name': 'Analogical',
        'purpose': 'Simplify the complex through a vivid image.',
        'procedures': 'Short, striking analogy.',
        'when_to_use': 'Opening hook, vulgarizing a concept.',
        'avoid_if': (
            'Never used alone — complement only. A bad analogy clouds '
            'the message.'
        ),
    },
    'APHORISTIC': {
        'name': 'Aphoristic',
        'purpose': 'Strike with a short, memorable formula.',
        'procedures': 'Punchline, maxim.',
        'when_to_use': 'Climax, closing sentence.',
        'avoid_if': 'Overuse kills clarity.',
    },
}


# =============================================================================
# MODE → DOMINANT REGISTER MAPPING (§5.2)
# =============================================================================

MODE_TO_DOMINANT_REGISTER = {
    'DISCOVERY': 'NARRATIVE',
    'CONVICTION': 'DELIBERATIVE',
    'PROOF': 'DEMONSTRATIVE',
    'DECISION': 'DELIBERATIVE',
}


# =============================================================================
# MATURITY MODULATIONS (§5.3)
# =============================================================================

MATURITY_MODULATIONS = {
    'solution_trust_low': {
        'dimension': 'solution_trust',
        'statuses': ('unclear', 'missing_evidence'),
        'instruction': (
            'Prioritize demonstrative register (proof, concrete case). '
            'Ban emphatic or epideictic tone — it increases distrust.'
        ),
    },
    'urgency_absent': {
        'dimension': 'urgency',
        'statuses': ('missing_evidence',),
        'instruction': (
            'Use light deliberative register: surface the cost of the '
            'status quo without forcing. Do not pressure.'
        ),
    },
    'felt_pain_unproven': {
        'dimension': 'felt_pain',
        'statuses': ('unclear', 'missing_evidence'),
        'instruction': (
            'Use moderate narrative register combined with elicitation '
            'questions. Make the stakeholder articulate the pain — do '
            'not assert it for them.'
        ),
    },
    'process_actor': {
        'dimension': None,
        'statuses': (),
        'instruction': (
            'When the stakeholder is a process actor (CFO, procurement): '
            'strict demonstrative register focused on THEIR decision '
            'criteria (the Metric), never product pains.'
        ),
    },
}


# =============================================================================
# MIXING RULES (§5.2)
# =============================================================================

MIXING_RULES = (
    '1 dominant register + at most 1 secondary register per brief '
    '(e.g. demonstrative to prove + deliberative for the next step). '
    'Beyond that, the message becomes incoherent — strictly forbidden.'
)


# =============================================================================
# GUARDRAILS — HARD RULES (§5.4)
# =============================================================================

GUARDRAILS = [
    (
        'NO RHETORIC LABELS IN OUTPUT. Never name a register, rhetorical '
        'device, or classical term (no "logos", "genus grande", '
        '"pathos"). The register manifests as a concrete gesture, never '
        'as a label.'
    ),
    (
        'NO ADVICE WITHOUT EVIDENCE. Every recommendation must be '
        'anchored in a signal or proof from the input pack. When '
        'evidence is missing, convert the advice into a discovery '
        'question instead.'
    ),
    (
        'GROUNDED REFORMULATIONS ONLY. Make a real number tangible '
        '(e.g. "10h/week = one month/year lost to consolidation"). '
        'Never use gratuitous metaphors or poetic imagery.'
    ),
    (
        'NEXT STEP = CONCRETE, DATED COMMITMENT. Never "I\'ll get back '
        'to you". Always propose a mobilizing action to secure during '
        'the call: which meeting, with whom, two date options on the '
        'spot.'
    ),
    (
        'EVIDENCE-BASED ONLY. Do not predict, do not invent intentions. '
        'Everything stated must trace back to captured evidence.'
    ),
    (
        'COACH TONE — DIRECT, BRIEF. No filler, no platitudes. '
        '"Ask open-ended questions" is banned. Every sentence must '
        'carry actionable weight.'
    ),
]
