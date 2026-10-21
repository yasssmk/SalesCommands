// frontend/src/components/signals/peopleEvidencePill.js
//
// TD-279 UI — People evidence check → pill mapping, the SAME pattern as
// signalStatusPill.js ({ label, role } consumed by StatusPill's status mode).
// Keyed on PeopleSignal.metadata.evidence_check.status (server check of the
// source_quote, backend services/people_evidence.py). Role "warning": an
// INFORMATION for the rep, never a technical error (UX_UI_Guidelines.md).
// "ok" (and a missing check) is absent on purpose → StatusPill renders nothing.

export const PEOPLE_EVIDENCE_PILL = {
  quote_not_found: { label: "Quote not found in the transcript", role: "warning" },
  quote_not_about_person: { label: "Quote does not concern this person", role: "warning" },
};

export default PEOPLE_EVIDENCE_PILL;
