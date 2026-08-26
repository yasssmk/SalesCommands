// frontend/src/components/signals/detail/ObjectiveDetailBlock.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Shared primitives
import DrawerSection from "components/display/DrawerSection";
import DrawerFieldRow from "components/display/DrawerFieldRow";

// Days threshold — matches backend OBJECTIVE_TARGET_DATE_SOON_DAYS.
const TARGET_DATE_SOON_DAYS = 90;

// Classify a target date into an urgency descriptor (label + chip colour).
// Single source of truth for objective urgency, shared by the drawer and
// the rich ObjectiveCard.
export function classifyTargetDate(isoDate) {
  if (!isoDate) return null;

  const target = new Date(isoDate);
  if (Number.isNaN(target.getTime())) return null;

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  target.setHours(0, 0, 0, 0);

  const diffDays = Math.round(
    (target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24),
  );

  if (diffDays < 0) return { label: "Overdue", color: "error" };
  if (diffDays === 0) return { label: "Due today", color: "error" };
  if (diffDays <= TARGET_DATE_SOON_DAYS) {
    return { label: `In ${diffDays}d`, color: "warning" };
  }
  return { label: `In ${diffDays}d`, color: "default" };
}

function formatDate(isoDate) {
  if (!isoDate) return null;
  try {
    return new Date(isoDate).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return isoDate;
  }
}

function ownerLine(signal) {
  if (signal.scope_level === "PERSONAL") {
    const c = signal.target_contact;
    const name = c ? `${c.first_name ?? ""} ${c.last_name ?? ""}`.trim() : "";
    return name ? `Owned by ${name}` : null;
  }
  if (signal.scope_level === "DEPARTMENT") {
    const deptName = signal.target_department?.name;
    return deptName ? `Department: ${deptName}` : null;
  }
  return null;
}

/**
 * ObjectiveDetailBlock — shared rendering of an ObjectiveSignal's
 * type-specific fields (target date + urgency, success criteria, owner).
 * Cross-type fields (scope, axes, status) live in the shell/header.
 */
export default function ObjectiveDetailBlock({ signal }) {
  const targetLabel = formatDate(signal.target_date);
  const urgency = classifyTargetDate(signal.target_date);
  const success = signal.success_criteria;
  const owner = ownerLine(signal);

  if (!targetLabel && !success && !owner) return null;

  return (
    <DrawerSection title="OBJECTIVE">
      {targetLabel && (
        <DrawerFieldRow label="Target date">
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            <Typography variant="body2">{targetLabel}</Typography>
            {urgency && urgency.color !== "default" && (
              <Chip
                label={urgency.label}
                size="small"
                color={urgency.color}
                variant="outlined"
                sx={{ height: 18, fontSize: "0.65rem" }}
              />
            )}
          </Stack>
        </DrawerFieldRow>
      )}
      <DrawerFieldRow label="Success criteria" value={success} />
      <DrawerFieldRow label="Owner" value={owner} />
    </DrawerSection>
  );
}

ObjectiveDetailBlock.propTypes = {
  signal: PropTypes.shape({
    target_date: PropTypes.string,
    success_criteria: PropTypes.string,
    scope_level: PropTypes.string,
    target_contact: PropTypes.object,
    target_department: PropTypes.shape({ name: PropTypes.string }),
  }).isRequired,
};
