// frontend/src/sections/activities/signals/wizard/forms/buildEditInitialValues.js
/**
 * Build Formik initialValues for an edit form, given a backend signal
 * read object and its concrete type.
 *
 * Each per-type builder mirrors exactly the fields of its matching
 * Inline*Form component. Catalog / contact-related objects are passed
 * whole — the matching Async* selectors expect the full option object
 * as their value prop, not a UUID string. This avoids a re-fetch loop
 * to re-hydrate the selection on edit.
 *
 * source_activity is NOT a builder field
 * --------------------------------------
 * A signal is always created from an activity context — the wizard
 * injects source_activity into the dispatch payload via extraPayload.
 * No inline form surfaces a picker for it, and no edit builder sets
 * an initial value for it. In edit mode, source_activity is preserved
 * server-side because PATCH is partial — sending no source_activity
 * leaves the existing FK untouched.
 *
 * @param {'pain'|'objective'|'impact'|'tech-stack'} signalType
 * @param {Object} signal - Backend read object for the signal
 * @returns {Object} Formik-ready initialValues
 */

export function buildEditInitialValues(signalType, signal) {
  if (!signal) return {};

  switch (signalType) {
    case "pain":
      return buildPainInitialValues(signal);
    case "objective":
      return buildObjectiveInitialValues(signal);
    case "impact":
      return buildImpactInitialValues(signal);
    case "tech-stack":
      return buildTechStackInitialValues(signal);
    default:
      return {};
  }
}

// ==============================|| PAIN ||============================== //

/**
 * @param {Object} signal - PainSignal read object
 * @returns {Object}
 *
 * Pain is a pure qualitative diagnosis. All impact-related data
 * (level, impacted_contact/department, human_impact, metric, etc.)
 * lives on PainImpact — captured separately via AddPainImpactDialog
 * in the Account Workspace, NOT in the wizard form.
 *
 * This builder mirrors exactly the fields of InlinePainForm:
 *   - Diagnosis  : summary, what, dimension
 *   - Narrative  : source_quote, notes
 *   - Cross-ref  : related_techstack, related_techstack_mention
 *                  (visible only when what === 'TECH')
 *
 * Catalog objects are passed whole — AsyncTechCatalogSelect expects the
 * full option object as its value prop, not a UUID string. This avoids
 * a re-fetch loop to re-hydrate the selection on edit.
 *
 * Cross-reference fields:
 *   - related_techstack          : object whole | null
 *                                  Backend exposes a compact catalog
 *                                  payload via the _PainDisplayMixin
 *                                  (id + company_name + product_name +
 *                                  is_competitor + is_integration_target)
 *                                  — directly usable by AsyncTechCatalogSelect.
 *   - related_techstack_mention  : free-text string (max 200 chars)
 *
 * Both fields are emitted unconditionally — InlinePainForm's render
 * decides visibility based on `what === 'TECH'`. A signal with
 * what=DATA referencing a BI tool will still surface its cross-ref
 * if both fields were set during a prior `what=TECH` state.
 */
function buildPainInitialValues(signal) {
  return {
    // Diagnosis
    summary: signal.summary ?? "",
    what: signal.what ?? "",
    dimension: signal.dimension ?? "",

    // Optional narrative extras
    source_quote: signal.source_quote ?? "",
    notes: signal.notes ?? "",

    // Cross-reference — TechStack
    related_techstack: signal.related_techstack ?? null,
    related_techstack_mention: signal.related_techstack_mention ?? "",
  };
}

// ==============================|| OBJECTIVE ||============================== //

/**
 * @param {Object} signal - ObjectiveSignal read object
 * @returns {Object}
 *
 * Objective is a flat structured goal — no child sub-resource, no impacts.
 * This builder mirrors exactly the fields exposed by the 3-section
 * InlineObjectiveForm:
 *
 *   S1 — Goal:    summary, what, dimension
 *   S2 — Scope:   scope_level + conditional target_contact OR target_department
 *   S3 — Success: success_criteria, target_date, notes
 *
 * Field shape notes:
 *   - target_contact passed whole — AsyncContactSelect expects the full
 *     option object as its value prop, not a UUID string.
 *   - target_department extracted to its id for MUI Select value binding.
 *   - target_date kept as ISO yyyy-mm-dd string (backend DateField
 *     serialises to that format natively; HTML5 <input type="date">
 *     binds directly to the string).
 */
function buildObjectiveInitialValues(signal) {
  return {
    // S1 — Goal
    summary: signal.summary ?? "",
    what: signal.what ?? "",
    dimension: signal.dimension ?? "",

    // S2 — Scope + conditional target
    scope_level: signal.scope_level ?? "",
    target_contact: signal.target_contact ?? null,
    target_department: signal.target_department?.id ?? "",

    // S3 — Success
    success_criteria: signal.success_criteria ?? "",
    target_date: signal.target_date ?? "",
    notes: signal.notes ?? "",
  };
}

// ==============================|| IMPACT ||============================== //

/**
 * @param {Object} signal - ImpactSignal read object
 * @returns {Object}
 *
 * Impact is a quantifiable evidence signal anchored on the same canonical
 * axes (what × dimension) as Pain and Objective, with a scope_level for
 * organisational reach but NO target_* owner FKs (Impact does not
 * propagate ownership).
 *
 * This builder mirrors exactly the 4-section InlineImpactForm:
 *
 *   S1 — Diagnosis:        summary, what, dimension
 *   S2 — Characterisation: impact_type (REQUIRED), human_impact, metric_text
 *   S3 — Scope:            scope_level
 *   S4 — Narrative:        source_quote, notes
 *
 * Field shape notes:
 *   - impact_type is REQUIRED on the backend (null=False) — the LLM
 *     pipeline always sets it at extraction time, so a read object
 *     should never have it null. Defensive ?? "" guards against
 *     malformed reads.
 *   - human_impact is nullable — '' represents "not set" in the form
 *     and gets coerced to null at submit time (see InlineImpactForm).
 *   - metric_text is nullable free text. Defensive ?? "" so the
 *     TextField binds to a string, never null.
 *   - scope_level is null=False with default=BUSINESS on the model;
 *     the LLM extractor forces BUSINESS by default — the rep can
 *     promote it via Edit.
 *
 * NO target_* fields — Impact has no owner FK (contrary to Objective).
 * NO target_date / success_criteria — Impact is the evidence itself,
 * not a goal to reach.
 *
 * source_activity is NOT a builder field — see file docstring.
 */
function buildImpactInitialValues(signal) {
  return {
    // S1 — Diagnosis
    summary: signal.summary ?? "",
    what: signal.what ?? "",
    dimension: signal.dimension ?? "",

    // S2 — Characterisation
    impact_type: signal.impact_type ?? "",
    human_impact: signal.human_impact ?? "",
    metric_text: signal.metric_text ?? "",

    // S3 — Scope
    scope_level: signal.scope_level ?? "",

    // S4 — Narrative
    source_quote: signal.source_quote ?? "",
    notes: signal.notes ?? "",
  };
}

// ==============================|| TECH STACK ||============================== //

/**
 * @param {Object} signal - TechStackSignal read object
 * @returns {Object}
 *
 * TechStackSignal is anchored to a tenant-level TechCatalog entry
 * with structured lifecycle + scope. The previous flat-field model
 * (tech_name / category / satisfaction / usage / limitations /
 * workarounds / integrations / source_department / source_quote /
 * signal_category) has been removed entirely from the backend.
 *
 * This builder mirrors exactly the 5-section InlineTechStackForm:
 *
 *   S1 — tech_catalog_entry            (object, immutable on Update)
 *   S2 — usage_scope, usage_department (conditional)
 *   S3 — usage_start_year, renewal_date, cost_description
 *   S4 — is_discontinued, discontinued_date (conditional)
 *   S5 — source_quote, notes           (narrative)
 *
 * Field shape notes:
 *   - tech_catalog_entry passed whole — AsyncTechCatalogSelect expects
 *     the full option object as its value prop, not a UUID string.
 *     The List/Detail serializers expose it as a compact dict
 *     ({ id, company_name, product_name, is_competitor,
 *        is_integration_target }) — directly usable by the picker.
 *   - usage_department extracted to its id for MUI Select binding.
 *   - usage_start_year kept as raw number or '' (Yup transform handles
 *     the empty-string → null coercion at submit time).
 *   - renewal_date / discontinued_date kept as ISO yyyy-mm-dd strings
 *     for HTML5 <input type="date">.
 *   - is_discontinued is a strict boolean — defensive ?? false in case
 *     the backend ever returns null.
 */
function buildTechStackInitialValues(signal) {
  return {
    // S1 — Catalog anchor (object whole)
    tech_catalog_entry: signal.tech_catalog_entry ?? null,

    // S2 — Scope axis
    usage_scope: signal.usage_scope ?? "",
    usage_department: signal.usage_department?.id ?? "",

    // S3 — Lifecycle stats
    usage_start_year:
      signal.usage_start_year !== null && signal.usage_start_year !== undefined
        ? signal.usage_start_year
        : "",
    renewal_date: signal.renewal_date ?? "",
    cost_description: signal.cost_description ?? "",

    // S4 — Discontinuation
    is_discontinued: signal.is_discontinued ?? false,
    discontinued_date: signal.discontinued_date ?? "",

    // S5 — Narrative
    source_quote: signal.source_quote ?? "",
    notes: signal.notes ?? "",
  };
}
