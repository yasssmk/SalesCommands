# app_modules/ai_pipelines/services/safety_filter.py
"""
Shared LLM-output safety filter for extraction pipelines.

This module exists so that every extractor (TranscriptSignalExtractor,
NextStepExtractor, future variants) applies the SAME epistemic policy
on the raw signals emitted by the LLM before any row is persisted:

  * Drop signals whose self-declared `confidence` is missing,
    non-numeric, or below the per-pipeline threshold.
  * Drop signals whose self-declared `is_inferred` is True when the
    pipeline's `DROP_INFERRED` knob is True (verbatim-anchored
    extractors).

Thresholds are not hardcoded here — they live as class attributes on
each Pipeline subclass (CONFIDENCE_MIN, DROP_INFERRED) and are passed
into `passes_safety_filter()` per call so a future use case (e.g.
sentiment analysis with a tolerant filter) can override without
touching this module.

Why module-level functions (not a base class)
---------------------------------------------
Both helpers are pure functions of their inputs — no state, no
dispatch logic, no per-instance config. Wrapping them in an abstract
base class to be subclassed would have created an awkward inheritance
("NextStepExtractor extends TranscriptSignalExtractor") without
behavioural benefit. Plain module-level functions keep the policy in
one obvious place and let any extractor import them directly.

Privacy
-------
Filter decisions are NOT logged at INFO/WARN by this module — the
calling extractor is the one that emits a single aggregated
`dropped_count` per stage into `AIPipelineRun.sub_calls`. Per-signal
drop reasons would either leak transcript content into logs or
clutter audit rows; both are avoided by design.
"""


def passes_safety_filter(raw, confidence_min, drop_inferred):
    """
    Apply the LLM self-declared safety filter to one raw signal dict.

    Drop rules (return False on any of them):
      - `confidence` missing or non-numeric.
      - `confidence` < confidence_min.
      - drop_inferred is True AND `is_inferred` is True (strict True
        comparison: a missing or falsy value does NOT trigger the drop,
        only an explicit boolean True).

    Args:
        raw:             dict -- one signal as emitted by the LLM.
        confidence_min:  float -- per-pipeline threshold below which a
                                   signal is dropped.
        drop_inferred:   bool -- if True, drop signals where
                                  is_inferred is explicitly True.

    Returns:
        bool: True when the signal passes the filter; False to drop.
    """
    raw_conf = raw.get('confidence')
    if raw_conf is None:
        # Per schema, confidence is required. Missing == contract violation.
        return False
    try:
        confidence = float(raw_conf)
    except (TypeError, ValueError):
        return False
    if confidence < confidence_min:
        return False

    if drop_inferred:
        # Strict True comparison: a missing or falsy value does not
        # trigger the drop, only an explicit boolean True.
        if raw.get('is_inferred') is True:
            return False

    return True


def safe_float(value, default=0.0):
    """
    Convert `value` to float; return `default` on failure (None,
    non-numeric string, TypeError).

    Used by extractors to coerce the LLM-emitted `confidence` into a
    persistable float on the signal row, even when the LLM produced an
    unexpected shape. Note this is the persistence-time coercion --
    upstream the same value already passed `passes_safety_filter` so
    a non-numeric value should not reach here in practice; the
    coercion is defence-in-depth.
    """
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
