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
 * usage (ONE line — the using departments if any, else the scale),
 * lifecycle (used since / renewal / cost),
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
  // WHO uses the tool — multi-department (M2M). Every write path
  // (extraction and manual entry) fills usage_departments; the legacy
  // single usage_department FK was dropped. Each entry is a compact
  // { id, name } payload.
  const departments = Array.isArray(signal.usage_departments)
    ? signal.usage_departments
    : [];

  // ONE usage line (PO rule). The department is the WHO and PRIMES over the
  // usage_scope SCALE: when at least one department is designated, show the
  // department list and NOT the scale (they contradict — "Company-wide" +
  // "Marketing" side by side made no sense). Otherwise fall back to the
  // scale. Never both. Plain text (comma-separated), same DrawerFieldRow
  // text style as "Used since" / "Cost" below — no chips.
  const departmentNames = departments.map((d) => d && d.name).filter(Boolean);
  const usageValue =
    departmentNames.length > 0
      ? departmentNames.join(", ")
      : usageScope || null;
  const usageLabel =
    departmentNames.length > 1
      ? "Departments"
      : departmentNames.length === 1
        ? "Department"
        : "Usage scope";

  const usedSince = signal.usage_start_year ? String(signal.usage_start_year) : null;
  const renewal = formatDate(signal.renewal_date);
  const cost = signal.cost_description;
  const discontinuedLabel = signal.is_discontinued
    ? `Discontinued${signal.discontinued_date ? ` (${formatDate(signal.discontinued_date)})` : ""}`
    : null;

  const hasContent =
    qualifications.length > 0 ||
    usageValue ||
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
      <DrawerFieldRow label={usageLabel} value={usageValue} />
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
    usage_departments: PropTypes.arrayOf(
      PropTypes.shape({ id: PropTypes.string, name: PropTypes.string })
    ),
    usage_start_year: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    renewal_date: PropTypes.string,
    cost_description: PropTypes.string,
    is_discontinued: PropTypes.bool,
    discontinued_date: PropTypes.string,
  }).isRequired,
};
