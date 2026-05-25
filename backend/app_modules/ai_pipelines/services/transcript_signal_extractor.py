# app_modules/ai_pipelines/services/transcript_signal_extractor.py
"""
TranscriptSignalExtractor -- per-stage persistence service for the
TranscriptSignalsPipeline.

Responsibility
--------------
Given a list of raw signal dicts emitted by the LLM for ONE pipeline
stage (pain / objective / impact / techstack), this service:

  1. Filters out LLM-self-declared weak signals (safety filter on
     confidence + is_inferred -- thresholds passed in from the
     pipeline class attributes).
  2. Builds a SignalManager.create() data dict per surviving signal,
     applying stage-specific mappings:
        - Pain        -> 1:1 passthrough.
        - Objective   -> 1:1 passthrough + force scope_level=BUSINESS
                          (and target_contact / target_department stay
                          unset, satisfying ObjectiveSignal.clean()'s
                          BUSINESS branch).
        - Impact      -> 1:1 passthrough + force scope_level=BUSINESS;
                          metric_text and human_impact left unset (rep
                          fills during validation). impact_type is
                          emitted by the LLM and persisted directly.
        - TechStack   -> XOR resolution of tech_catalog_entry_id /
                          tech_name_raw, with defense-in-depth on the
                          catalog UUID (must belong to the requesting
                          tenant); usage_scope filtered to TEAM /
                          COMPANY / UNKNOWN (DEPARTMENT and unknown
                          values demoted to null).
  3. Calls SignalManager.create() for each surviving signal.
  4. Returns the persisted list and the dropped count for audit
     logging by the pipeline.

Drop counting
-------------
Every signal that does not result in a persisted row increments the
`dropped_count`, regardless of the reason: safety-filter rejection,
malformed LLM emission, cross-tenant UUID, validation failure from
SignalManager.create(). The pipeline only needs the integer; granular
reasons live in module logs (WARN level) for ops investigation.

Defense in depth -- TechCatalog tenant isolation
------------------------------------------------
The LLM receives the TechCatalog list filtered to activity.client_id
(see _build_techcatalog_block in context.py). However, the LLM could
still hallucinate a UUID, or a malicious prompt could attempt to
exfiltrate by emitting a UUID from another tenant. Before assigning
`tech_catalog_entry`, this service re-validates the UUID by querying
TechCatalog.objects.get(id=..., client_id=activity.client_id) -- any
mismatch leads to a silent drop with a WARNING log.

Concurrency / atomicity
-----------------------
Each SignalManager.create() runs as its own implicit Django save()
transaction. We deliberately do NOT wrap the batch in a single
transaction.atomic(): we WANT partial success when one signal fails
validation -- the others should still be persisted and surfaced to
the rep for review.

Statelessness
-------------
The extractor holds no per-instance state. `persist_stage()` is
effectively a classmethod with `self`. We keep it as an instance
method for symmetry with future variants (e.g. a v2 extractor with
a different filter strategy could subclass).
"""

import logging
import uuid as uuid_module

from django.utils import timezone

from app_modules.signals.constants import (
    ScopeLevel,
    SignalSource,
    SignalStatus,
)
from app_modules.signals.services.signal_manager import SignalManager
from app_modules.tech_catalog.models import TechCatalog
from core.exceptions import StandardizedValidationError


logger = logging.getLogger(__name__)


# Allowed values for TechStack usage_scope at v1. Defines which strings
# the LLM may emit and have them propagate to the model. Any other value
# (including "DEPARTMENT", which would require a usage_department FK we
# don't extract) is demoted to None.
_TECHSTACK_USAGE_SCOPE_ALLOWED = {'TEAM', 'COMPANY', 'UNKNOWN'}


class TranscriptSignalExtractor:
    """
    Stage-by-stage persistence for the TranscriptSignalsPipeline.

    Usage:
        extractor = TranscriptSignalExtractor()
        persisted, dropped = extractor.persist_stage(
            stage='pain',
            raw_signals=[...],
            activity=activity,
            user=user,
            client_id=client_id,
            confidence_min=0.5,
            drop_inferred=True,
        )
    """

    # =========================================================================
    # MAIN ENTRY
    # =========================================================================

    def persist_stage(
        self,
        *,
        stage,
        raw_signals,
        activity,
        user,
        client_id,
        confidence_min,
        drop_inferred,
    ):
        """
        Apply safety filter + persist surviving signals for one stage.

        Args:
            stage:           'pain' | 'objective' | 'impact' | 'techstack'.
            raw_signals:     list[dict] -- the LLM's emitted signals.
            activity:        app_modules.activities.Activity -- source activity.
            user:            end_users.User -- the rep who triggered the run.
            client_id:       UUID -- tenant scope.
            confidence_min:  float -- LLM signals with confidence < this are
                                       dropped (safety filter).
            drop_inferred:   bool -- if True, drop signals where
                                       is_inferred is True.

        Returns:
            tuple (persisted, dropped_count)
                persisted:     list of concrete signal instances
                                (PainSignal / ObjectiveSignal /
                                ImpactSignal / TechStackSignal).
                dropped_count: int -- total signals NOT persisted, all reasons
                                combined. The pipeline logs this in
                                AIPipelineRun.sub_calls.
        """
        if not isinstance(raw_signals, list):
            logger.warning(
                'persist_stage_invalid_input',
                extra={
                    'stage': stage,
                    'type': type(raw_signals).__name__,
                    'event': 'ai_pipeline_persist',
                },
            )
            return [], 0

        persisted = []
        dropped_count = 0

        for raw in raw_signals:
            if not isinstance(raw, dict):
                dropped_count += 1
                continue

            # --- Safety filter ---
            if not self._passes_safety_filter(raw, confidence_min, drop_inferred):
                dropped_count += 1
                continue

            # --- Build the create() data dict ---
            data = self._build_signal_data(
                stage=stage,
                raw=raw,
                activity=activity,
                client_id=client_id,
            )
            if data is None:
                # Malformed signal or defense-in-depth violation
                # (logged inside the builder).
                dropped_count += 1
                continue

            # --- Persist via SignalManager ---
            try:
                signal = SignalManager.create(
                    data=data,
                    user=user,
                    client_id=client_id,
                )
                persisted.append(signal)
            except StandardizedValidationError as exc:
                logger.warning(
                    'signal_create_validation_failed',
                    extra={
                        'stage': stage,
                        'error': str(exc),
                        'event': 'ai_pipeline_persist',
                    },
                )
                dropped_count += 1
            except Exception as exc:
                # Defensive catch-all: a malformed raw value could trigger
                # a model-level ValidationError or a programming bug.
                # Per-signal failure must not abort the batch.
                logger.error(
                    'signal_create_unexpected_error',
                    extra={
                        'stage': stage,
                        'error': str(exc),
                        'event': 'ai_pipeline_persist',
                    },
                    exc_info=True,
                )
                dropped_count += 1

        return persisted, dropped_count

    # =========================================================================
    # SAFETY FILTER
    # =========================================================================

    @staticmethod
    def _passes_safety_filter(raw, confidence_min, drop_inferred):
        """
        Apply the LLM self-declared safety filter.

        Drop rules:
          - `confidence` missing or non-numeric                 -> drop.
          - `confidence` < confidence_min                       -> drop.
          - drop_inferred is True AND `is_inferred` is True     -> drop.

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

    # =========================================================================
    # DATA-DICT BUILDERS
    # =========================================================================

    def _build_signal_data(self, *, stage, raw, activity, client_id):
        """
        Dispatch to the per-stage data-dict builder.

        Returns:
            dict ready for SignalManager.create(), or None on malformed input.
        """
        if stage == 'pain':
            return self._build_pain_data(raw, activity)
        if stage == 'objective':
            return self._build_objective_data(raw, activity)
        if stage == 'impact':
            return self._build_impact_data(raw, activity)
        if stage == 'techstack':
            return self._build_techstack_data(raw, activity, client_id)

        logger.warning(
            'persist_stage_unknown_stage',
            extra={'stage': stage, 'event': 'ai_pipeline_persist'},
        )
        return None

    # ---------------------- Pain ----------------------

    def _build_pain_data(self, raw, activity):
        """
        Build SignalManager.create() data for a Pain signal.

        Schema requirements (from pain_v1.py):
            what, dimension, summary, source_quote, confidence, is_inferred
        """
        required = ('what', 'dimension', 'summary', 'source_quote')
        if not all(k in raw and raw[k] is not None for k in required):
            return None

        return {
            'signal_type':     'pain',
            'account':         activity.account,
            'source_activity': activity,
            'source':          SignalSource.LLM_EXTRACTED,
            'status':          SignalStatus.PENDING,
            'what':            raw['what'],
            'dimension':       raw['dimension'],
            'summary':         raw['summary'],
            'source_quote':    raw['source_quote'],
            'confidence':      self._safe_float(raw.get('confidence')),
            'is_inferred':     bool(raw.get('is_inferred')),
        }

    # ---------------------- Objective ----------------------

    def _build_objective_data(self, raw, activity):
        """
        Build SignalManager.create() data for an Objective signal.

        Schema requirements (from objective_v1.py):
            what, dimension, summary, source_quote, confidence, is_inferred

        BUSINESS-scope hardcoded fields (v1):
            scope_level         = ScopeLevel.BUSINESS
            target_contact      = (unset, defaults to None)
            target_department   = (unset, defaults to None)
        """
        required = ('what', 'dimension', 'summary', 'source_quote')
        if not all(k in raw and raw[k] is not None for k in required):
            return None

        return {
            'signal_type':     'objective',
            'account':         activity.account,
            'source_activity': activity,
            'source':          SignalSource.LLM_EXTRACTED,
            'status':          SignalStatus.PENDING,
            'what':            raw['what'],
            'dimension':       raw['dimension'],
            'summary':         raw['summary'],
            'source_quote':    raw['source_quote'],
            'confidence':      self._safe_float(raw.get('confidence')),
            'is_inferred':     bool(raw.get('is_inferred')),

            # v1 hardcoded scope -- rep refines during validation.
            'scope_level':     ScopeLevel.BUSINESS,
        }
    
    # ---------------------- Impact ----------------------

    def _build_impact_data(self, raw, activity):
        """
        Build SignalManager.create() data for an Impact signal.

        Schema requirements (from impact_v1.py):
            what, dimension, impact_type, summary, source_quote,
            confidence, is_inferred.

        impact_type is REQUIRED at the model level (ImpactSignal.clean())
        and emitted on every signal by the LLM. Missing or null
        impact_type -> drop the signal.

        BUSINESS-scope hardcoded fields (v1):
            scope_level    = ScopeLevel.BUSINESS  (rep promotes during
                                                    validation)

        Optional Impact fields left unset (rep adds during validation):
            metric_text    -- free-text quantified value; LLM
                              normalisation of fuzzy units is brittle
                              at MVP scope.
            human_impact   -- fuzzy emotion qualifier (FRUSTRATION /
                              OVERLOAD / STRESS / DEMOTIVATION /
                              CONFLICT); mapping a quote to a precise
                              category yields too much noise at MVP.

        These defaults satisfy ImpactSignal.clean()'s required-fields
        rule (source_activity NOT NULL; impact_type / what / dimension /
        summary / scope_level all populated).
        """
        required = ('what', 'dimension', 'impact_type', 'summary', 'source_quote')
        if not all(k in raw and raw[k] is not None for k in required):
            return None

        return {
            'signal_type':     'impact',
            'account':         activity.account,
            'source_activity': activity,
            'source':          SignalSource.LLM_EXTRACTED,
            'status':          SignalStatus.PENDING,
            'what':            raw['what'],
            'dimension':       raw['dimension'],
            'impact_type':     raw['impact_type'],
            'summary':         raw['summary'],
            'source_quote':    raw['source_quote'],
            'confidence':      self._safe_float(raw.get('confidence')),
            'is_inferred':     bool(raw.get('is_inferred')),

            # v1 hardcoded scope -- rep refines during validation.
            'scope_level':     ScopeLevel.BUSINESS,

            # metric_text and human_impact NOT extracted in v1 -- rep
            # fills during validation. The fields are nullable on the
            # model, so omitting them from the data dict is safe.
        }

    # ---------------------- TechStack ----------------------

    def _build_techstack_data(self, raw, activity, client_id):
        """
        Build SignalManager.create() data for a TechStack signal.

        Schema requirements (from techstack_v1.py):
            tech_catalog_entry_id OR tech_name_raw (XOR),
            usage_scope (optional),
            source_quote, confidence, is_inferred.

        XOR resolution:
            * Both set            -> contract violation, drop.
            * Neither set         -> contract violation, drop.
            * catalog_id set      -> validate against tenant catalog
                                      (defense in depth). Hallucinated /
                                      cross-tenant UUID -> drop.
            * tech_name_raw set   -> persist tech_catalog_entry=None
                                      and metadata['pending_tech_name']=raw.

        usage_scope filtering:
            * "TEAM" / "COMPANY" / "UNKNOWN"  -> propagate to model.
            * Anything else (incl. "DEPARTMENT", which the v1 prompt
              forbids but the LLM may emit anyway) or missing
              -> demote to None. usage_department stays unset,
              satisfying TechStackSignal.clean() rule 2.

        source_quote is required (schema). Missing -> drop.
        """
        if not raw.get('source_quote'):
            return None

        catalog_id = raw.get('tech_catalog_entry_id')
        tech_name_raw = raw.get('tech_name_raw')

        # XOR enforcement.
        has_catalog = catalog_id is not None and catalog_id != ''
        has_raw     = tech_name_raw is not None and str(tech_name_raw).strip() != ''
        if has_catalog and has_raw:
            logger.warning(
                'techstack_xor_violation_both_set',
                extra={
                    'catalog_id': str(catalog_id),
                    'tech_name_raw': str(tech_name_raw),
                    'event': 'ai_pipeline_persist',
                },
            )
            return None
        if not has_catalog and not has_raw:
            return None

        data = {
            'signal_type':     'tech_stack',
            'account':         activity.account,
            'source_activity': activity,
            'source':          SignalSource.LLM_EXTRACTED,
            'status':          SignalStatus.PENDING,
            'source_quote':    raw['source_quote'],
            'confidence':      self._safe_float(raw.get('confidence')),
            'is_inferred':     bool(raw.get('is_inferred')),
        }

        # --- Resolve catalog FK with defense-in-depth ---
        if has_catalog:
            entry = self._resolve_catalog_uuid(catalog_id, client_id)
            if entry is None:
                # Hallucinated UUID, cross-tenant attempt, or malformed UUID.
                # _resolve_catalog_uuid logged the cause; we drop the signal.
                return None
            data['tech_catalog_entry'] = entry
        else:
            # Raw name fallback. Catalog FK stays null (allowed for PENDING
            # LLM_EXTRACTED -- see TechStackSignal.clean() rule 1).
            data['tech_catalog_entry'] = None
            data['metadata'] = {
                'pending_tech_name': str(tech_name_raw).strip(),
            }

        # --- usage_scope filtering ---
        usage_scope_raw = raw.get('usage_scope')
        if usage_scope_raw in _TECHSTACK_USAGE_SCOPE_ALLOWED:
            data['usage_scope'] = usage_scope_raw
        # else: leave unset (None) -- model field is nullable.

        return data

    # =========================================================================
    # DEFENSE-IN-DEPTH HELPERS
    # =========================================================================

    @staticmethod
    def _resolve_catalog_uuid(catalog_id, client_id):
        """
        Resolve a TechCatalog UUID to its model instance, with tenant
        isolation enforcement.

        The LLM is fed a tenant-scoped catalog (see context.py) but a
        prompt-injection attempt or model hallucination could still
        produce a UUID that does not belong to the requesting tenant.
        This helper is the second line of defense.

        Returns:
            TechCatalog instance on success.
            None on:
                * malformed UUID string
                * UUID not found in the tenant's catalog (cross-tenant
                  or hallucinated)

        Failures are WARN-logged for ops investigation.
        """
        # Validate UUID shape.
        try:
            catalog_uuid = uuid_module.UUID(str(catalog_id))
        except (ValueError, TypeError, AttributeError):
            logger.warning(
                'techstack_catalog_uuid_malformed',
                extra={
                    'catalog_id': str(catalog_id),
                    'event': 'ai_pipeline_defense_in_depth',
                },
            )
            return None

        # Tenant-scoped lookup.
        try:
            return TechCatalog.objects.get(
                id=catalog_uuid,
                client_id=client_id,
            )
        except TechCatalog.DoesNotExist:
            logger.warning(
                'techstack_catalog_uuid_cross_tenant_or_hallucination',
                extra={
                    'catalog_id': str(catalog_uuid),
                    'client_id': str(client_id),
                    'event': 'ai_pipeline_defense_in_depth',
                },
            )
            return None

    # =========================================================================
    # MISC HELPERS
    # =========================================================================

    @staticmethod
    def _safe_float(value, default=0.0):
        """Convert value to float; return default on failure."""
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default