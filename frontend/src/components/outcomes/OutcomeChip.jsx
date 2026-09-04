// frontend/src/components/outcomes/OutcomeChip.jsx
//
// O-1 — the shared OUTCOME chip. Renders an outcome's unified label + palette
// role colour on the standard StatusPill (outline look: role.main text/border on
// a background.paper ground), consistent with the status pill. Meant to replace
// the 3 inline outcome chips later (not migrated here).

"use client";

import PropTypes from "prop-types";

import StatusPill from "components/chips/StatusPill";
import { OUTCOME_META } from "utils/outcomes";

export default function OutcomeChip({ outcome, sx }) {
  const meta = outcome ? OUTCOME_META[outcome] : null;
  if (!meta) return null;

  return (
    <StatusPill
      label={meta.label}
      colorText={`${meta.role}.main`}
      colorBg="background.paper"
      sx={sx}
    />
  );
}

OutcomeChip.propTypes = {
  /** An ActivityOutcome value (e.g. "SUCCESSFUL"). Empty → renders nothing. */
  outcome: PropTypes.string,
  sx: PropTypes.object,
};
