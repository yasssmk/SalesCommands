// frontend/src/utils/objectiveScope.js
//
// SIG-5b — configuration + mapping for the Objective "scope pill".
//
// The Objective scope is a single backend enum `scope_level`
// (backend constants.py ScopeLevel: BUSINESS / DEPARTMENT / PERSONAL) plus a
// conditional FK: `target_department` for DEPARTMENT, `target_contact` for
// PERSONAL (backend objective_signal.py clean()).
//
// Product decision (SIG-5b): the pill offers only TWO states — Company
// (=BUSINESS) and Department (=DEPARTMENT). PERSONAL is no longer offered, but
// it is NOT removed from the backend enum: an objective already stored as
// PERSONAL is shown read-only (a third, non-clickable pill) so its data is not
// silently changed.
//
// This module is the single source of truth for the pill states, their scope
// mapping and their palette-token colours (no hex). Imported by
// components/signals/ObjectiveScopePill.jsx.

// Backend ScopeLevel values (mirror of backend constants.py:437-439). Kept as a
// named map so callers never inline the raw strings.
export const OBJECTIVE_SCOPE = {
  BUSINESS: "BUSINESS",
  DEPARTMENT: "DEPARTMENT",
  PERSONAL: "PERSONAL",
};

// The scopes OFFERED by the pill, in display order. PERSONAL is intentionally
// absent (legacy read-only). `label` is the product wording (Company, not
// Business).
export const SCOPE_PILL_OPTIONS = [
  { key: OBJECTIVE_SCOPE.BUSINESS, label: "Company" },
  { key: OBJECTIVE_SCOPE.DEPARTMENT, label: "Department" },
];

// Read-only label for an existing PERSONAL objective (shown, never offered).
export const PERSONAL_LEGACY_LABEL = "Personal";

// Derive the active scope from a signal's scope_level. Empty / unknown → BUSINESS
// (the model default, hardcoded at creation in objective_v1.py).
export function deriveScopeState(scopeLevel) {
  if (scopeLevel === OBJECTIVE_SCOPE.DEPARTMENT) return OBJECTIVE_SCOPE.DEPARTMENT;
  if (scopeLevel === OBJECTIVE_SCOPE.PERSONAL) return OBJECTIVE_SCOPE.PERSONAL;
  return OBJECTIVE_SCOPE.BUSINESS;
}

// Build the DRAFT patch when a pill is chosen. It clears the FKs the target
// scope FORBIDS at the model layer (backend clean(): BUSINESS → neither
// target_department nor target_contact; DEPARTMENT → no target_contact), so the
// assembled PATCH is backend-valid whatever the objective's prior scope was
// (incl. switching a legacy PERSONAL objective). The department id itself is
// emitted separately by the department select.
export function scopePatch(scopeKey) {
  if (scopeKey === OBJECTIVE_SCOPE.DEPARTMENT) {
    return { scope_level: OBJECTIVE_SCOPE.DEPARTMENT, target_contact: null };
  }
  return {
    scope_level: OBJECTIVE_SCOPE.BUSINESS,
    target_department: null,
    target_contact: null,
  };
}

// Pill colours as palette-path tokens (resolved by MUI sx / StatusPill — no hex).
// Active = primary role; inactive = muted on the paper ground (same convention
// as OutcomeChip: role.main text/border on background.paper).
export const SCOPE_PILL_COLORS = {
  active: { colorText: "primary.main", colorBg: "primary.lighter" },
  inactive: { colorText: "text.secondary", colorBg: "background.paper" },
};
