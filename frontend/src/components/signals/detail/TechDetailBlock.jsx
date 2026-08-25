// frontend/src/components/signals/detail/TechDetailBlock.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Shared primitives
import DrawerSection from "components/display/DrawerSection";
import DrawerFieldRow from "components/display/DrawerFieldRow";

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

/**
 * TechDetailBlock — shared rendering of a TechStackSignal's type-specific
 * fields: qualification flags (competitor / integration / to-replace),
 * usage (scope + department), lifecycle (used since / renewal / cost),
 * and discontinuation. Reads booleans and *_display off the signal.
 * The tool name is the signal's identity (rendered by the shell/header),
 * not part of this block.
 */
export default function TechDetailBlock({ signal }) {
  const qualifications = [
    signal.is_competitor && { key: "competitor", label: "Competitor", color: "error" },
    signal.is_integration && { key: "integration", label: "Integration", color: "info" },
    signal.is_to_replace && { key: "to-replace", label: "To replace", color: "warning" },
  ].filter(Boolean);

  const usageScope = signal.usage_scope_display;
  const department = signal.usage_department?.name;
  const usedSince = signal.usage_start_year ? String(signal.usage_start_year) : null;
  const renewal = formatDate(signal.renewal_date);
  const cost = signal.cost_description;
  const discontinuedLabel = signal.is_discontinued
    ? `Discontinued${signal.discontinued_date ? ` (${formatDate(signal.discontinued_date)})` : ""}`
    : null;

  const hasContent =
    qualifications.length > 0 ||
    usageScope ||
    department ||
    usedSince ||
    renewal ||
    cost ||
    discontinuedLabel;

  if (!hasContent) return null;

  return (
    <DrawerSection title="TOOL USAGE">
      {qualifications.length > 0 && (
        <DrawerFieldRow label="Qualification">
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
            {qualifications.map((q) => (
              <Chip
                key={q.key}
                label={q.label}
                size="small"
                color={q.color}
                variant="outlined"
                sx={{ height: 20, fontSize: "0.7rem" }}
              />
            ))}
          </Stack>
        </DrawerFieldRow>
      )}
      <DrawerFieldRow label="Usage scope" value={usageScope} />
      <DrawerFieldRow label="Department" value={department} />
      <DrawerFieldRow label="Used since" value={usedSince} />
      <DrawerFieldRow label="Renewal date" value={renewal} />
      <DrawerFieldRow label="Cost" value={cost} />
      {discontinuedLabel && (
        <DrawerFieldRow label="Status">
          <Typography variant="body2" color="error.main">
            {discontinuedLabel}
          </Typography>
        </DrawerFieldRow>
      )}
    </DrawerSection>
  );
}

TechDetailBlock.propTypes = {
  signal: PropTypes.shape({
    is_competitor: PropTypes.bool,
    is_integration: PropTypes.bool,
    is_to_replace: PropTypes.bool,
    usage_scope_display: PropTypes.string,
    usage_department: PropTypes.shape({ name: PropTypes.string }),
    usage_start_year: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    renewal_date: PropTypes.string,
    cost_description: PropTypes.string,
    is_discontinued: PropTypes.bool,
    discontinued_date: PropTypes.string,
  }).isRequired,
};
