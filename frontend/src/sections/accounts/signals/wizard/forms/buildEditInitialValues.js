// frontend/src/sections/accounts/signals/wizard/forms/buildEditInitialValues.js
/**
 * buildEditInitialValues — maps a backend signal read object to Formik initialValues.
 *
 * One function per signal type, dispatched by signalType string.
 *
 * Contact fields (source_contact, target_contact):
 *   Backend returns { id, first_name, last_name, job_title }.
 *   AsyncContactSelect accepts this shape directly as its value prop.
 *   No transformation needed — passed as-is (or null if absent).
 *
 * Department fields (source_department, impacted_department, target_department):
 *   Backend returns { id, name } objects.
 *   MUI Select stores a UUID string — we extract .id.
 *
 * All optional fields default to "" (empty string) for controlled inputs,
 * except contact fields which default to null (AsyncContactSelect expects null).
 *
 * @param {'people'|'pain'|'objective'|'tech-stack'} signalType
 * @param {Object} signal - Signal read object from the backend
 * @returns {Object} Formik initialValues
 */
export function buildEditInitialValues(signalType, signal) {
  if (!signal) return {};

  switch (signalType) {
    case "people":
      return buildPeopleInitialValues(signal);
    case "pain":
      return buildPainInitialValues(signal);
    case "objective":
      return buildObjectiveInitialValues(signal);
    case "tech-stack":
      return buildTechStackInitialValues(signal);
    default:
      return {};
  }
}

// ==============================|| PEOPLE ||============================== //

/**
 * @param {Object} signal - PeopleSignal read object
 * @returns {Object}
 */
function buildPeopleInitialValues(signal) {
  return {
    role: signal.role ?? "",
    influence_level: signal.influence_level ?? "",
    // Contact objects passed as-is — AsyncContactSelect expects { id, ... } | null
    target_contact: signal.target_contact ?? null,
    // Department objects: extract id for MUI Select
    target_department: signal.target_department?.id ?? "",
    notes: signal.notes ?? "",
    source_contact: signal.source_contact ?? null,
    source_department: signal.source_department?.id ?? "",
    source_quote: signal.source_quote ?? "",
    signal_category: signal.signal_category ?? "",
  };
}

// ==============================|| PAIN ||============================== //

/**
 * @param {Object} signal - PainSignal read object
 * @returns {Object}
 *
 * Pain is now a pure qualitative diagnosis. All impact-related data
 * (pain_level, impacted_contact/department, human_impact, business_cost,
 * impact_summary) lives on PainImpact — captured separately via
 * AddPainImpactDialog in the Account Workspace, NOT in the wizard form.
 *
 * This builder mirrors exactly the 7 fields of the simplified InlinePainForm:
 *   what, dimension, summary            → canonical + narrative
 *   source_contact, source_activity     → required provenance (objects)
 *   source_quote, notes                 → optional narrative extras
 *
 * Contact and activity objects are passed whole — AsyncContactSelect and
 * AsyncActivitySelect both expect the full object as their value prop, not
 * a UUID string. This avoids a re-fetch loop to re-hydrate the selection.
 */
function buildPainInitialValues(signal) {
  return {
    // Diagnosis
    summary: signal.summary ?? "",
    what: signal.what ?? "",
    dimension: signal.dimension ?? "",

    // Source — objects passed whole; the wizard extracts UUIDs at dispatch time
    source_contact: signal.source_contact ?? null,
    source_activity: signal.source_activity ?? null,

    // Optional narrative extras
    source_quote: signal.source_quote ?? "",
    notes: signal.notes ?? "",
  };
}
// ==============================|| OBJECTIVE ||============================== //

/**
 * @param {Object} signal - ObjectiveSignal read object
 * @returns {Object}
 */
function buildObjectiveInitialValues(signal) {
  return {
    summary: signal.summary ?? "",
    goal_level: signal.goal_level ?? "",
    source_contact: signal.source_contact ?? null,
    success_criteria: signal.success_criteria ?? "",
    measurement_method: signal.measurement_method ?? "",
    target_contact: signal.target_contact ?? null,
    target_department: signal.target_department?.id ?? "",
    notes: signal.notes ?? "",
    source_department: signal.source_department?.id ?? "",
    source_quote: signal.source_quote ?? "",
    signal_category: signal.signal_category ?? "",
  };
}

// ==============================|| TECH STACK ||============================== //

/**
 * @param {Object} signal - TechStackSignal read object
 * @returns {Object}
 */
function buildTechStackInitialValues(signal) {
  return {
    source_contact: signal.source_contact ?? null,
    tech_name: signal.tech_name ?? "",
    category: signal.category ?? "",
    usage: signal.usage ?? "",
    satisfaction: signal.satisfaction ?? "",
    limitations: signal.limitations ?? "",
    workarounds: signal.workarounds ?? "",
    integrations: signal.integrations ?? "",
    // renewal_date: backend returns ISO date string (YYYY-MM-DD) or null
    renewal_date: signal.renewal_date ?? "",
    source_department: signal.source_department?.id ?? "",
    source_quote: signal.source_quote ?? "",
    signal_category: signal.signal_category ?? "",
  };
}
