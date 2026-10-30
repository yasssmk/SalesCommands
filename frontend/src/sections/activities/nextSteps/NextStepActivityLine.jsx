// frontend/src/sections/activities/nextSteps/NextStepActivityLine.jsx
//
// Sprint Next steps 5.3 — the 3rd line (SignalLine `extra`) of a RESOLVED next
// step: "→ title · type · date · status pill" of the activity created from it OR
// linked to it. Clicking it opens that activity (never the signal drawer). The
// status pill is the shared StatusPill with the activity status tables, as in
// the activity header.

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";

// Project imports
import StatusPill from "components/chips/StatusPill";
import { formatShortDate } from "components/signals/SignalLine";
import {
  ACTIVITY_TYPE_LABELS,
  ACTIVITY_STATUS_LABELS,
  ACTIVITY_STATUS_CHIP_COLORS,
} from "api/accounts/activities";

/** The activity a next step is resolved by — created from it or linked to it. */
export function getResolvedActivity(signal) {
  return signal?.linked_activity || signal?.attached_activity || null;
}

export default function NextStepActivityLine({ activity, onOpen }) {
  const meta = [
    ACTIVITY_TYPE_LABELS[activity.activity_type] || activity.activity_type_display,
    formatShortDate(activity.scheduled_date || activity.due_date),
  ].filter(Boolean);
  const pill =
    ACTIVITY_STATUS_CHIP_COLORS[activity.status] || ACTIVITY_STATUS_CHIP_COLORS.PLANNED;

  return (
    <Box
      role="link"
      tabIndex={0}
      aria-label={`Open activity ${activity.title}`}
      onClick={(e) => {
        e.stopPropagation(); // the activity, never the signal drawer
        onOpen(activity.id);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          e.stopPropagation();
          onOpen(activity.id);
        }
      }}
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 1,
        flexWrap: "wrap",
        cursor: "pointer",
        "&:hover .next-step-activity-title": { textDecoration: "underline" },
      }}
    >
      <Typography variant="caption" color="text.secondary" sx={{ minWidth: 0 }}>
        {"→ "}
        <Box
          component="span"
          className="next-step-activity-title"
          sx={{ color: "primary.main", fontWeight: 500 }}
        >
          {activity.title}
        </Box>
        {meta.length > 0 && ` · ${meta.join(" · ")}`}
      </Typography>
      <StatusPill
        label={ACTIVITY_STATUS_LABELS[activity.status] || activity.status_display || activity.status}
        colorText={pill.text}
        colorBg={pill.background}
      />
    </Box>
  );
}

NextStepActivityLine.propTypes = {
  /** The compact activity of the next step serializer (linked_activity / attached_activity). */
  activity: PropTypes.shape({
    id: PropTypes.string.isRequired,
    title: PropTypes.string,
    activity_type: PropTypes.string,
    activity_type_display: PropTypes.string,
    status: PropTypes.string,
    status_display: PropTypes.string,
    scheduled_date: PropTypes.string,
    due_date: PropTypes.string,
  }).isRequired,
  /** (activityId) => void — opens the activity. */
  onOpen: PropTypes.func.isRequired,
};
