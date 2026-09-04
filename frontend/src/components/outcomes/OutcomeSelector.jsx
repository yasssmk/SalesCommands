// frontend/src/components/outcomes/OutcomeSelector.jsx
//
// O-1 — the shared OUTCOME pill selector. Renders getOutcomesForType(activityType)
// as single-select pills built on the standard StatusPill: unselected = outline
// (role.main text/border on background.paper), selected = filled (role.contrastText
// on role.main). Generic — knows nothing about campaign/deal, and does NOT handle
// the callback date (that belongs to the drawer in O-2). Theme tokens only.

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";

// Project
import StatusPill from "components/chips/StatusPill";
import { OUTCOME_META, getOutcomesForType } from "utils/outcomes";

export default function OutcomeSelector({ activityType, value, onChange, exclude = [], sx }) {
  const outcomes = getOutcomesForType(activityType).filter((o) => !exclude.includes(o));

  return (
    <Box
      data-testid="outcome-selector"
      sx={{ display: "flex", flexWrap: "wrap", gap: 1, ...sx }}
    >
      {outcomes.map((outcome) => {
        const meta = OUTCOME_META[outcome];
        const selected = value === outcome;
        return (
          <StatusPill
            key={outcome}
            component="button"
            type="button"
            data-testid={`outcome-pill-${outcome}`}
            aria-pressed={selected}
            onClick={() => onChange(outcome)}
            label={meta.label}
            colorText={selected ? `${meta.role}.contrastText` : `${meta.role}.main`}
            colorBg={selected ? `${meta.role}.main` : "background.paper"}
            sx={{
              cursor: "pointer",
              font: "inherit",
              // keep a crisp role-coloured edge in both states (selected fill uses
              // contrastText for its label, so pin the border to role.main).
              borderColor: `${meta.role}.main`,
            }}
          />
        );
      })}
    </Box>
  );
}

OutcomeSelector.propTypes = {
  /** Activity type (CALL/EMAIL/MEETING/DEMO/TASK/LINKEDIN/OTHER) — filters the pills. */
  activityType: PropTypes.string,
  /** Currently selected outcome value (single select). */
  value: PropTypes.string,
  /** Raised with the clicked outcome value. */
  onChange: PropTypes.func.isRequired,
  /** Outcome values to hide on top of the type filter (e.g. CALLBACK on a deal). */
  exclude: PropTypes.arrayOf(PropTypes.string),
  sx: PropTypes.object,
};
