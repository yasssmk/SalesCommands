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

export function getContact(signal) {
  return signal.contact || signal.source_context?.contacts?.[0] || null;
}

export function formatContact(contact) {
  if (!contact) return null;
  const name = `${contact.first_name ?? ""} ${contact.last_name ?? ""}`.trim();
  return name || null;
}

export function getNextStepSummary(signal) {
  return signal?.suggested_title || "Untitled suggestion";
}

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

export function getConstraintSummary(signal) {
  return signal.summary || "—";
}
