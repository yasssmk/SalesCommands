# app_modules/ai_pipelines/prompts/transcript_signals/pain_impact_v1.py
"""
Request layer for the MERGED Pain + Impact extraction (v1) -- Sprint A2.

Why a single stage
------------------
Pain and Impact are a CAUSE -> CONSEQUENCE pair. Splitting them across two
independent LLM calls (the pre-A2 pain_v1 / impact_v1 stages) forced the
model to re-read the same passage twice and made the cause/consequence
frontier fuzzy: a figure ("40k/quarter") could leak into a pain, or a bare
cause ("the system is slow") could be padded with an invented number.

This module asks the model to read the whole passage ONCE and sort every
fragment into the right bucket:

  * IMPACT = the measurable CONSEQUENCE (the WHAT): a number, a loss, a
    duration, a human consequence (10h/week, 40k/quarter, turnover,
    burnout). A METRIC IS ALWAYS AN IMPACT, NEVER A PAIN.
  * PAIN = the WHY of that consequence (the CAUSE): what explains it -- the
    system is slow, the process is manual, the data is scattered. A PAIN
    NEVER carries a figure.

Mental model surfaced in the prompt: "[A] wants to reach [B: objective], but
[C: pain] prevents it, and as a result [D] suffers [E: impact]." This stage
emits C (the pain / cause) and E (the impact / measurable cost). Objective B
is a DIFFERENT sub-call (objective_v1) -- objectives are NOT emitted here.

Output schema (v1)
------------------
ONE JSON object with two arrays::

    {
      "pains":   [ {what, dimension, scope_level, target_department,
                    summary, source_quote, confidence, is_inferred}, ... ],
      "impacts": [ {what, dimension, impact_type, scope_level,
                    target_department, summary, source_quote,
                    confidence, is_inferred}, ... ]
    }

The pain object schema is exactly the pain_v1 field set; the impact object
schema is exactly the impact_v1 field set (it additionally carries
`impact_type`). Empty result is `{"pains": [], "impacts": []}`.

Independent scope
-----------------
scope_level (BUSINESS | DEPARTMENT, never PERSONAL) is decided per signal by
the A1 subject-not-speaker rule. The PAIN takes the scope of who HAS the
problem; the IMPACT takes the scope of who BEARS the cost -- they MAY differ
(a department's problem can cost the whole company). target_department is
drawn from the controlled StandardDepartment vocabulary and resolved by an
exact name lookup in the extractor.

Persistence contract
--------------------
The pipeline splits the parsed object and calls the UNCHANGED persistence
service twice:

    persist_stage(stage='pain',   raw_signals=parsed['pains'],   ...)
    persist_stage(stage='impact', raw_signals=parsed['impacts'], ...)

so `_build_pain_data` / `_build_impact_data`, the scope resolver + guards,
the response keys (`pain` / `impact`), and every downstream consumer stay
exactly as they were. This module only changes the LLM CALL: one call
instead of two.

Marker note (test harness)
--------------------------
The TASK header says "Extract PAIN and IMPACT signals" -- deliberately
distinct from the legacy "Extract PAIN signals" / "Extract IMPACT signals"
markers so the test FakeProvider's stage inference maps this to the merged
'pain_impact' stage rather than mis-matching a legacy stage.

Versioning
----------
PAIN_IMPACT_PROMPT_VERSION is captured in AIPipelineRun.prompt_versions
under the single 'pain_impact' key.
"""


__all__ = ['PAIN_IMPACT_PROMPT_VERSION', 'build_pain_impact_request']


PAIN_IMPACT_PROMPT_VERSION = 'v1'


def build_pain_impact_request(transcript):
    """
    Build the request layer for the merged Pain + Impact extraction call.

    Args:
        transcript: str -- the full transcript text pasted by the rep.
            Sent verbatim to the LLM (no sanitisation here -- the
            data-exposure contract with the LLM provider is governed
            at the legal layer via DPA, not in this module).

    Returns:
        str: A ready-to-concatenate request block. Will be combined
        with the context layer by PromptBuilder.assemble() to form the
        final user message.
    """
    return f"""TASK
Extract PAIN and IMPACT signals from the SALES TRANSCRIPT below, in a single pass.

Pain and Impact are a CAUSE -> CONSEQUENCE pair. Read each passage once and sort:
- An IMPACT is the measurable CONSEQUENCE (the WHAT): a number, a loss, a duration,
  a human consequence (e.g. "10h/week", "40k/quarter", "high turnover", "burnout").
  A METRIC IS ALWAYS AN IMPACT, NEVER A PAIN.
- A PAIN is the WHY of that consequence (the CAUSE): what explains it -- the system
  is slow, the process is manual, the data is scattered. A PAIN NEVER carries a figure.

Mental model: "[A] wants to reach [B: objective], but [C: pain] prevents it, and as
a result [D] suffers [E: impact]." Here you emit C (the pain / cause) and E (the
impact / measurable cost). Objective B is a DIFFERENT extraction -- do NOT emit
objectives here.

SORTING TEST (apply to each fragment)
- "a measurable consequence?"          -> IMPACT.
- "the reason / cause of a consequence?" -> PAIN.
- "[cause], so [consequence]"          -> emit a PAIN (the cause) AND an IMPACT
  (the consequence), each anchored on its OWN source_quote. NEVER put the figure
  in the pain.

PARTIAL EMISSION (be honest, never invent)
- A pain stated without its cost    -> emit the pain alone.
- An impact stated without its cause -> emit the impact alone.
- NEVER invent a missing figure or a missing cause. Extraction is factual.

SCOPE (decided independently for each signal)
- `scope_level` MUST be exactly BUSINESS or DEPARTMENT, decided ONLY by the SUBJECT
  of that signal -- which perimeter it concerns -- NEVER by who is speaking. The
  PAIN takes the scope of who HAS the problem; the IMPACT takes the scope of who
  BEARS the cost, and these MAY differ.
- DEPARTMENT = the signal names or clearly identifies one specific department (use
  that department verbatim from the `target_department` list in the context), even
  if the speaker belongs to another department. BUSINESS = no specific department is
  named; the observation is company-wide or cross-departmental. A senior person
  (CEO, GM, C-level) describing one department is still DEPARTMENT. Never emit
  PERSONAL or any other value.
- `target_department` is REQUIRED when scope_level is DEPARTMENT (one value from the
  context list) and MUST be null when scope_level is BUSINESS.

OUTPUT SCHEMA
Return a single JSON object with this exact shape:

{{
  "pains": [
    {{
      "what":         "<one value from the `what` list in the CANONICAL TAXONOMY>",
      "dimension":    "<one value from the `dimension` list in the CANONICAL TAXONOMY>",
      "scope_level":  "<BUSINESS or DEPARTMENT>",
      "target_department": "<one value from the `target_department` list when DEPARTMENT, else null>",
      "summary":      "<one short sentence rephrasing the pain (cause) in your own words, ~200 chars or less>",
      "source_quote": "<verbatim excerpt stating the CAUSE -- no figure>",
      "confidence":   <float in [0.0, 1.0], self-declared per the EPISTEMIC FILTER>,
      "is_inferred":  <boolean, true when inferred rather than directly stated>
    }}
  ],
  "impacts": [
    {{
      "what":         "<one value from the `what` list in the CANONICAL TAXONOMY>",
      "dimension":    "<one value from the `dimension` list in the CANONICAL TAXONOMY>",
      "impact_type":  "<one value from the `impact_type` list in the CANONICAL TAXONOMY>",
      "scope_level":  "<BUSINESS or DEPARTMENT>",
      "target_department": "<one value from the `target_department` list when DEPARTMENT, else null>",
      "summary":      "<one short sentence rephrasing the impact (consequence) in your own words, ~200 chars or less>",
      "source_quote": "<verbatim excerpt stating the measurable CONSEQUENCE>",
      "confidence":   <float in [0.0, 1.0], self-declared per the EPISTEMIC FILTER>,
      "is_inferred":  <boolean, true when inferred rather than directly stated>
    }}
  ]
}}

If NO pain evidence AND NO impact evidence is present anywhere in the transcript,
return exactly: {{"pains": [], "impacts": []}}

DOMAIN vs DIMENSION (applies to every pain AND every impact -- `what` is NEVER a dimension word)
- `what` is the DOMAIN: the business AREA concerned. It MUST be EXACTLY one code
  from the `what` list in the CANONICAL TAXONOMY (OPS / TECH / DATA / PEOPLE /
  GROWTH). Never invent a value, and never put a dimension word (cost / time /
  quality / scale / risk) in `what`.
- `dimension` is the MEASURE AXIS: Cost, Time, Quality, Scale, Risk. A word like
  "cost / coût", "time / temps" or "quality" is ALWAYS a dimension, NEVER a `what`.
- When an observation is about operations and mentions a cost, `what`="OPS" and the
  cost goes into `dimension`="COST" -- never `what`="COST".

WHAT x DIMENSION EXAMPLES (domain code first, measure axis second)
- "operational costs keep climbing"        -> what="OPS"    (Operations / Process), dimension="COST"    (Cost / Budget)
- "the sales cycle drags on"                -> what="GROWTH" (Growth / Revenue),     dimension="TIME"    (Time / Speed)
- "the reporting data is inaccurate"        -> what="DATA"   (Data / Visibility),    dimension="QUALITY" (Quality / Accuracy)

EMISSION RULES
- Apply the EVIDENCE RULES and EPISTEMIC FILTER from the system prompt to BOTH
  arrays: drop weak inferences and NEVER fabricate.
- `summary` must be your own rephrasing. Never copy-paste the source_quote.
- `source_quote` must be a verbatim excerpt from the transcript, preserving the
  original language, punctuation, and casing. Never translate.
- Multiple pains or impacts sharing the same (what, dimension) are allowed when each
  carries a DISTINCT source_quote.

FEW-SHOTS (the cause/consequence frontier + independent scope)
1) Passage: "the marketing data isn't reliable, it costs the company about 40k per quarter"
   -> "pains":   [ {{ scope_level="DEPARTMENT", target_department="Marketing",
                      source_quote="the marketing data isn't reliable" }} ]
      "impacts": [ {{ impact_type="FINANCIAL", scope_level="BUSINESS",
                      target_department=null,
                      source_quote="it costs the company about 40k per quarter" }} ]
   Note the INDEPENDENT scope: the pain is Marketing's problem (DEPARTMENT/Marketing),
   the cost is borne company-wide (BUSINESS). The figure is on the IMPACT, never the pain.

2) Passage: "the system is slow"
   -> "pains":   [ {{ source_quote="the system is slow" }} ]
      "impacts": []
   A cause with no measurable consequence stated -> pain alone. Do NOT invent a cost.

3) Passage: "IT spends 10h a week on this"
   -> "pains":   []
      "impacts": [ {{ impact_type="TIME", source_quote="IT spends 10h a week on this" }} ]
   A measurable consequence with no cause stated -> impact alone. A figure is an
   IMPACT, never a PAIN.

TRANSCRIPT
<<<TRANSCRIPT_START>>>
{transcript}
<<<TRANSCRIPT_END>>>
"""
