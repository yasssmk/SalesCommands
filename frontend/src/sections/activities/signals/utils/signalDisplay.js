// frontend/src/sections/activities/signals/utils/signalDisplay.js

/**
 * Display name for a tech-stack signal.
 *
 * S10: the tool is identified by free text on the signal itself
 * (`tech_name`). This used to prefer a `tech_catalog_entry` payload and
 * fall back to `metadata.pending_tech_name`, flagging the latter as
 * `pending` ("not in your tech catalog"). Both the catalogue and that
 * pending state are gone — there is no reference list left to be absent
 * from — so the object shape no longer carries a `pending` key.
 *
 * The object shape is kept (rather than returning a bare string) so the
 * four call sites keep reading `.name` unchanged.
 */
export function getTechSummary(signal) {
  return { name: signal?.tech_name?.trim() || "Unknown tool" };
}

// Backend TechStack UsageScope values (backend constants.py UsageScope — three
// cases since Sprint TechStack T0). Kept as a named map so callers never
// inline the raw strings (mirror of utils/objectiveScope OBJECTIVE_SCOPE).
export const USAGE_SCOPE = {
  DEPARTMENT: "DEPARTMENT",
  COMPANY: "COMPANY",
  UNKNOWN: "UNKNOWN",
};

// Sprint Next steps (PO rule 5.8c): a next step CITES names. The name it cites
// for one of its People: the People's full_name, else its contact's name.
export function getCitedPersonName(people) {
  const contact = people?.target_contact;
  return (
    people?.full_name ||
    `${contact?.first_name ?? ""} ${contact?.last_name ?? ""}`.trim()
  );
}

// A TechStack signal's usage, with the PO rule "the departments PRIME over the
// scale": when at least one usage department is designated, the department
// names are the usage and the scale is not shown. Shared by TechDetailBlock
// (DC / Account) and the Activity chassis detail so the rule lives once.
//   departmentNames — names of the usage departments ([] when none);
//   usageScope / usageScopeDisplay — the scale, ONLY when no department.
export function getTechUsage(signal) {
  const departments = Array.isArray(signal?.usage_departments)
    ? signal.usage_departments
    : [];
  const departmentNames = departments.map((d) => d && d.name).filter(Boolean);
  const hasDepartments = departmentNames.length > 0;
  return {
    departmentNames,
    usageScope: hasDepartments ? null : (signal?.usage_scope ?? null),
    usageScopeDisplay: hasDepartments ? null : (signal?.usage_scope_display ?? null),
  };
}

// The label of a usage scope value, read from the /signals/choices/
// usage_scopes list. Returns null when the choices are not loaded.
export function getUsageScopeLabel(value, choices) {
  return choices?.usage_scopes?.find((o) => o.value === value)?.label ?? null;
}

export function getContact(signal) {
  return signal.contact || signal.source_context?.contacts?.[0] || null;
}

// Joined display of a signal's MULTI-department scope. Pain / Impact /
// Constraint carry `target_departments` — an M2M list of {id, name} (the
// singular target_department FK was dropped for these types, backend migr.
// 0038/0041). This joins EVERY department name with ", " (e.g. "Sales,
// Marketing"). Returns null when the list is empty/absent, so a DrawerFieldRow
// drops the row — same empty-safe contract as formatContact. Objective / People
// keep the single target_department FK and do NOT use this.
export function formatTargetDepartments(signal) {
  const departments = signal?.target_departments;
  if (!Array.isArray(departments) || departments.length === 0) return null;
  return departments.map((d) => d?.name).filter(Boolean).join(", ") || null;
}

export function formatContact(contact) {
  if (!contact) return null;
  const name = `${contact.first_name ?? ""} ${contact.last_name ?? ""}`.trim();
  return name || null;
}

export function getNextStepSummary(signal) {
  return signal?.suggested_title || "Untitled suggestion";
}

// Renders a NextStepSignal's `suggested_contacts` for the next-step
// display surfaces (AISuggestionCard, NextStepSuggestionDrawer,
// SignalDetailCard/Content). Note: this is a DORMANT capability — the
// field is wired and displayable but the LLM extraction never populates
// it (TD-7), so in practice this returns "" today. That empty result is
// expected, not a bug; the empty-safe guard below is intentional.
export function formatSuggestedContacts(contacts) {
  if (!contacts || contacts.length === 0) return "";
  return contacts
    .map((c) => `${c.first_name || ""} ${c.last_name || ""}`.trim())
    .filter(Boolean)
    .join(" · ");
}

export function getPeopleSummary(signal) {
  const role = signal.role_display || signal.role || "";
  const contact = signal.target_contact;
  const dept = signal.target_department;
  const name = contact
    ? `${contact.first_name ?? ""} ${contact.last_name ?? ""}`.trim()
    : null;
  const deptName = dept?.name ?? null;
  if (name && deptName) return `${role} — ${name} (${deptName})`;
  if (name) return `${role} — ${name}`;
  if (deptName) return `${role} — ${deptName}`;
  return role || "—";
}

// A People signal's person name: the linked contact (first + last) first,
// else the full_name as stated, else the job title as said (TD-279 D,
// metadata.job_title -- "contrôleur de gestion"), else "Unnamed person".
// Shared by the detail headline and the Activity list line (People S4).
export function getPeopleName(signal) {
  return (
    formatContact(signal?.target_contact) ||
    signal?.full_name?.trim() ||
    signal?.metadata?.job_title?.trim() ||
    "Unnamed person"
  );
}

// People detail headline on the Activity chassis: "Name — Role (Department)".
// Distinct from getPeopleSummary above ("Role — Name (Dept)", contact-only
// name, no full_name) which SignalDetailCard keeps unchanged.
export function getPeopleHeadline(signal) {
  const name = getPeopleName(signal);
  const role = signal?.role_display || signal?.role || "";
  const deptName = signal?.target_department?.name ?? null;
  const head = role ? `${name} — ${role}` : name;
  return deptName ? `${head} (${deptName})` : head;
}

export function getConstraintSummary(signal) {
  return signal.summary || "—";
}
