// frontend/src/components/signals/signalStatusPill.js
//
// UI-1 — the SINGLE source of truth for a signal's status → pill mapping.
// Each status maps to a palette ROLE + a human label; StatusPill derives the
// pill colours from the role (`${role}.main` text/border on `${role}.lighter`
// background). Consumed by the drawer coque header (via openDrawer { status,
// statusMap }) and any other status-pill surface, so the mapping lives in ONE
// place instead of being re-declared inline.
//
// (Consolidates the identical inline maps previously duplicated in
// SignalDetailContent's local STATUS_PILL and the signal cards / SignalStatusChip;
// those can migrate onto this constant when they are next touched.)

export const SIGNAL_STATUS_PILL = {
  PENDING: { label: "Pending", role: "warning" },
  VALIDATED: { label: "Validated", role: "success" },
  REJECTED: { label: "Rejected", role: "error" },
};

export default SIGNAL_STATUS_PILL;
