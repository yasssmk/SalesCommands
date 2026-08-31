// frontend/src/components/signals/SignalLine.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import {
  UserOutlined,
  CalendarOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  StopOutlined,
} from "@ant-design/icons";

// Project imports
import SignalTypeChip from "components/chips/SignalTypeChip";
import { getTechSummary } from "sections/activities/signals/utils/signalDisplay";

// Light status treatment — reuses the design-system `light` Chip variant
// (tinted background + light border, see themes/overrides/Chip.js) with a
// small status icon. Semantic tints: pending = warning, validated = success,
// rejected = neutral/muted (rejection is a routine outcome, not an error —
// red is reserved for technical failures elsewhere in the app).
const STATUS_LIGHT = {
  PENDING: { label: "Pending", color: "warning", Icon: ClockCircleOutlined },
  VALIDATED: { label: "Validated", color: "success", Icon: CheckCircleOutlined },
  REJECTED: { label: "Rejected", color: "default", Icon: StopOutlined },
};

// ==============================|| HELPERS ||============================== //

// Signal types that carry an organisational scope axis (BUSINESS / DEPARTMENT).
// tech-stack (usage_scope is a different concept), blockers and next-steps
// carry no scope, so the scope chip is omitted for them.
const SCOPE_TYPES = new Set([
  "pain",
  "objective",
  "impact",
  "people",
  "constraints",
]);

function formatShortDate(dateStr) {
  if (!dateStr) return null;
  try {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

// The content field varies by signal type — there is no single serializer
// field common to all. Resolve the human message per type.
function getMessage(signal, signalType) {
  switch (signalType) {
    case "tech-stack":
      return getTechSummary(signal).name;
    case "next-steps":
      return signal.suggested_title || "Untitled suggestion";
    case "people":
      return signal.notes || "—";
    // pain / objective / impact / blockers / constraints
    default:
      return signal.summary || "—";
  }
}

// Scope chip label: "Business" by default, "Department · {name}" for a
// department-scoped signal. Returns null when the type carries no scope
// or the scope has not been set yet.
function getScopeLabel(signal, signalType) {
  if (!SCOPE_TYPES.has(signalType)) return null;
  // Constraint has NO scope_level column (detached from the axes) — its scope
  // is carried by target_department alone: DEPARTMENT when set, else BUSINESS.
  if (signalType === "constraints") {
    return signal.target_department?.name
      ? `Department · ${signal.target_department.name}`
      : "Business";
  }
  if (!signal.scope_level) return null;
  if (signal.scope_level === "DEPARTMENT") {
    return `Department · ${signal.target_department?.name ?? "—"}`;
  }
  return "Business";
}

// First activity contact rendered as "First Last · job_title · department".
function formatOriginContact(contact) {
  if (!contact) return null;
  const name = `${contact.first_name ?? ""} ${contact.last_name ?? ""}`.trim();
  const parts = [
    name || null,
    contact.job_title || null,
    contact.department?.name || null,
  ].filter(Boolean);
  return parts.join(" · ") || null;
}

// ==============================|| SIGNAL LINE ||============================== //

/**
 * Unified compact "signal line" for the flat signal views (Activity / DC /
 * Account). Renders every signal type from the raw list payload, which the
 * flat hooks tag with `_signalType` (passed here as `signalType`).
 *
 * The row is informational only — status + message + meta. It carries NO
 * lifecycle action buttons: every action (validate / reject / edit / reopen)
 * lives in the signal drawer. Clicking the row calls `onSelect` and the parent
 * opens that drawer, where the actions are performed.
 *
 * Layout:
 *   Line 1 — [type chip, when showTypeChip] + full message (wraps, no clamp).
 *   Line 2 — meta: date · contact · scope · light status chip.
 *
 * `showTypeChip` lets a caller hide the type chip when the surrounding section
 * already names the type (grouped views); flat views keep it (only type cue).
 */
export default function SignalLine({
  signal,
  signalType,
  onSelect,
  showTypeChip = true,
}) {
  const isRejected = signal.status === "REJECTED";

  const message = getMessage(signal, signalType);
  const scopeLabel = getScopeLabel(signal, signalType);
  const dateLabel = formatShortDate(signal.created_at);
  const statusConfig = STATUS_LIGHT[signal.status] ?? null;

  const contacts = signal.source_context?.contacts ?? [];
  const originContact = formatOriginContact(contacts[0]);
  const extraContacts = contacts.length > 1 ? contacts.length - 1 : 0;

  return (
    <Box
      data-testid="signal-line"
      role="button"
      tabIndex={0}
      aria-label="Open signal details"
      onClick={() => onSelect?.(signal, signalType)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect?.(signal, signalType);
        }
      }}
      sx={{
        display: "flex",
        flexDirection: "column",
        gap: 0.75,
        width: "100%",
        border: 1,
        borderColor: "divider",
        borderRadius: 1.5,
        px: 2,
        py: 1.25,
        mb: 1,
        cursor: "pointer",
        opacity: isRejected ? 0.6 : 1,
        transition: "background-color 0.12s, opacity 0.12s",
        "&:hover": { bgcolor: "action.hover" },
      }}
    >
      {/* Line 1: [type chip] · full message (wraps, no truncation) */}
      <Stack
        direction="row"
        alignItems="flex-start"
        gap={1}
        sx={{ width: "100%", minWidth: 0 }}
      >
        {showTypeChip && (
          <Box sx={{ flexShrink: 0, mt: 0.25 }}>
            <SignalTypeChip signalType={signalType} size="small" />
          </Box>
        )}

        {/* Message — full text, wraps to as many lines as needed. */}
        <Typography
          variant="body2"
          sx={{
            flexGrow: 1,
            minWidth: 0,
            fontWeight: 500,
            whiteSpace: "normal",
            overflowWrap: "anywhere",
          }}
        >
          {message}
        </Typography>
      </Stack>

      {/* Line 2 (meta): date · contact · scope · light status */}
      <Stack
        direction="row"
        alignItems="center"
        gap={1.5}
        flexWrap="wrap"
        sx={{ width: "100%" }}
      >
        {/* Date */}
        {dateLabel && (
          <Stack
            direction="row"
            spacing={0.5}
            alignItems="center"
            sx={{ flexShrink: 0 }}
          >
            <CalendarOutlined style={{ fontSize: 12, color: "#8c8c8c" }} />
            <Typography variant="caption" color="text.secondary" noWrap>
              {dateLabel}
            </Typography>
          </Stack>
        )}

        {/* Origin contact */}
        {originContact && (
          <Stack
            direction="row"
            spacing={0.5}
            alignItems="center"
            sx={{ flexShrink: 1, minWidth: 0, maxWidth: 320 }}
          >
            <UserOutlined style={{ fontSize: 12, color: "#8c8c8c" }} />
            <Typography variant="caption" color="text.secondary" noWrap>
              {originContact}
            </Typography>
            {extraContacts > 0 && (
              <Chip
                label={`+${extraContacts}`}
                size="small"
                variant="outlined"
                sx={{ height: 18, fontSize: "0.65rem" }}
              />
            )}
          </Stack>
        )}

        {/* Nature — constraint classification axis (Constraint only). */}
        {signalType === "constraints" && signal.nature_display && (
          <Chip
            label={signal.nature_display}
            size="small"
            variant="outlined"
            sx={{ height: 20, fontSize: "0.68rem", flexShrink: 0 }}
          />
        )}

        {/* Scope — moved here from the message line, where it was cramped. */}
        {scopeLabel && (
          <Chip
            label={scopeLabel}
            size="small"
            variant="outlined"
            sx={{ height: 20, fontSize: "0.68rem", flexShrink: 0 }}
          />
        )}

        {/* Spacer pushes the status to the right edge of the meta line. */}
        <Box sx={{ flexGrow: 1 }} />

        {/* Light status treatment (DS `light` Chip variant + icon). */}
        {statusConfig && (
          <Chip
            label={statusConfig.label}
            color={statusConfig.color}
            variant="light"
            size="small"
            icon={<statusConfig.Icon style={{ fontSize: 12 }} />}
            sx={{ height: 20, fontSize: "0.68rem", flexShrink: 0 }}
          />
        )}
      </Stack>
    </Box>
  );
}

SignalLine.propTypes = {
  signal: PropTypes.shape({
    id: PropTypes.string.isRequired,
    status: PropTypes.string.isRequired,
    summary: PropTypes.string,
    notes: PropTypes.string,
    suggested_title: PropTypes.string,
    tech_name: PropTypes.string,
    scope_level: PropTypes.string,
    nature_display: PropTypes.string,
    target_department: PropTypes.shape({
      id: PropTypes.string,
      name: PropTypes.string,
    }),
    created_at: PropTypes.string,
    source_context: PropTypes.shape({
      activity: PropTypes.shape({ id: PropTypes.string }),
      contacts: PropTypes.arrayOf(PropTypes.object),
    }),
  }).isRequired,
  signalType: PropTypes.oneOf([
    "pain",
    "objective",
    "impact",
    "tech-stack",
    "blockers",
    "next-steps",
    "people",
    "constraints",
    "competitors",
  ]).isRequired,
  onSelect: PropTypes.func,
  /** Hide the type chip when the surrounding section already names the type. */
  showTypeChip: PropTypes.bool,
};
