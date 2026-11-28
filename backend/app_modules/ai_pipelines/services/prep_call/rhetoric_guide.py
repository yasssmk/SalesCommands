# app_modules/ai_pipelines/services/prep_call/rhetoric_guide.py
"""
The Game Plan v2's persuasion guide (sprint 2 Game Plan, G10) — reduced to
what the v2 prompt uses, in sales words: no classical rhetoric label, no
brief mode (a single Game Plan mode since G10).

Pure data — no logic. Read by prompts/prep_call/system_v2.py.
The v1 brief's guide (modes, registers, mixing rules) is frozen in
prompts/prep_call/guide_v1.py, read by the v1 prompts only.
"""


# The balance of a Game Plan (PO): mostly applied selling, a measured share
# of persuasion.
PERSUASION_MIX = (
    'About 70% applied selling (discovery, qualification, the next step) and '
    '30% persuasion craft. The persuasion never shows as a technique: it is a '
    'concrete gesture — a question, a contrast, the client\'s own words.'
)

# The three ways a Game Plan convinces, named in sales words.
CONVICTION_LEVERS = (
    (
        'TRUST — earn the right to advise: show you understood their '
        'situation, and support a claim only with a reference, a '
        'certification or a fact that the seller profile or the deal '
        'actually gives.'
    ),
    (
        'FEELING — measured, never forced: bring back the urgent problems, '
        'the desire and the frustrations THEY expressed, in their words. '
        'Never dramatise, never assert a pain they did not state.'
    ),
    (
        'REASON — their own facts first: a figure, a delay or a cost is used '
        'only when it appears in the input; otherwise ask for it.'
    ),
)

# How the plan adapts to what the deal health says of the deal.
MATURITY_ADJUSTMENTS = (
    (
        'Credibility unclear or missing: lead with proof from the input (a '
        'reference, a case, a certification), never with enthusiasm.'
    ),
    (
        'Urgency missing: make the cost of the status quo visible through a '
        'question, without pressure.'
    ),
    (
        'Felt pain unproven: let the client say it — ask, do not assert.'
    ),
    (
        'A process actor (finance, procurement, legal): speak to THEIR '
        'decision criteria, not to product pains.'
    ),
)

# The hard rules of a Game Plan (on top of the output-language rule).
GUARDRAILS = (
    (
        'NEVER INVENT. No customer reference, no figure, no percentage, no '
        'delay, no product capability that is not in the input (the seller '
        'profile, the products, the deal health, the signals, the previous '
        'conversations). Without proof, build on what the client said, or '
        'turn the point into a discovery question. A saving such as "X% '
        'less maintenance saves N hours a week" is written ONLY when the '
        'input states it.'
    ),
    (
        'NO TECHNIQUE LABELS. Never name a rhetorical device or any classical '
        'Greek or Latin rhetoric term, nor an internal framework name: the '
        'technique shows as a gesture, never as a word.'
    ),
    (
        'FIRST NAMES ONLY. Refer to a person only by the label given in the '
        'input (a first name, or "P1 Marc (Finance)" for two people sharing '
        'a first name). Never write a last name, never invent a person.'
    ),
    (
        'THE NEXT STEP IS A COMMITMENT, AND WE KEEP CONTROL. A concrete '
        'action accepted during the conversation — which meeting, with whom, '
        'two date options — and who sends what: the seller keeps the lead. '
        'Never "I\'ll get back to you".'
    ),
    (
        'COACH TONE — DIRECT, BRIEF. Every sentence carries an action; no '
        'filler, no platitude ("ask open-ended questions" is banned).'
    ),
)


# =============================================================================
# v2.2 (sprint 2 Game Plan, G13f — PO decisions of 28/11), read by
# prompts/prep_call/system_v2_2.py. The rules above stay those of v2 / v2.1.
# =============================================================================

# Decision 1 — the next step and the closing: less precise, « closer ».
# Replaces, in v2.2, the v2 rule « THE NEXT STEP IS A COMMITMENT » (which
# asked for two date options).
NEXT_STEP_RULE = (
    'THE NEXT STEP IS THE NEXT LOGICAL STEP OF THEIR BUYING PROCESS: the one '
    'that validates the current step (its criteria, the missing information). '
    'The closing makes the rep get the person\'s agreement on that next step '
    'and lock it in during the conversation ("Get agreement on the security '
    'review and book it before hanging up"). No date, no time, no duration and '
    'no detailed content of the next meeting.'
)

# Decision 1 — the opening's time.
OPENING_TIME_RULE = (
    'THE TIME OF THE OPENING: confirm the time the person has; never invent a '
    'duration — reuse one only when the input gives it.'
)

# Decision 2 — readable in the middle of a meeting (the plan only).
def readability_rule(max_words):
    return (
        'READABLE AT A GLANCE: each item of a section is ONE short line, at most '
        f'{max_words} words, opening on an action verb (ask, confirm, get, show) — '
        'no paragraph. The context stays 2 to 3 short sentences.'
    )


# Decision 1 — the AI message.
MESSAGE_NEXT_EXCHANGE_RULE = (
    'THE MESSAGE PROPOSES TO AGREE ON A NEXT EXCHANGE, with no invented '
    'precision (no date, no time, no duration).'
)
