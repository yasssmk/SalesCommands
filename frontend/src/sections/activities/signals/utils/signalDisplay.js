// frontend/src/sections/activities/signals/utils/signalDisplay.js

export function getTechSummary(signal) {
  if (signal.tech_catalog_entry?.product_name) {
    return { name: signal.tech_catalog_entry.product_name, pending: false };
  }
  if (signal.metadata?.pending_tech_name) {
    return { name: signal.metadata.pending_tech_name, pending: true };
  }
  return { name: "Unknown tool", pending: false };
}

export function getContact(signal) {
  return signal.contact || signal.source_context?.contacts?.[0] || null;
}

export function formatContact(contact) {
  if (!contact) return null;
  const name = `${contact.first_name ?? ""} ${contact.last_name ?? ""}`.trim();
  return name || null;
}
