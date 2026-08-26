// frontend/src/components/signals/SignalLine.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import { UserOutlined, CalendarOutlined } from "@ant-design/icons";

// Project imports
import SignalStatusChip from "components/chips/SignalStatusChip";
import SignalTypeChip from "components/chips/SignalTypeChip";
import { getTechSummary } from "sections/activities/signals/utils/signalDisplay";

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
  if (!SCOPE_TYPES.has(signalType) || !signal.scope_level) return null;
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
 */
export default function SignalLine({
  signal,
  signalType,
  onSelect,
}) {
  const isRejected = signal.status === "REJECTED";

  const message = getMessage(signal, signalType);
  const scopeLabel = getScopeLabel(signal, signalType);
  const dateLabel = formatShortDate(signal.created_at);

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
      {/* Row 1: type chip · status chip · scope chip · message */}
      <Stack
        direction="row"
        alignItems="center"
        gap={1}
        sx={{ width: "100%", minWidth: 0 }}
      >
        <SignalTypeChip signalType={signalType} size="small" />
        <SignalStatusChip status={signal.status} size="small" />
        {scopeLabel && (
          <Chip label={scopeLabel} size="small" variant="outlined" />
        )}

        {/* Message — takes the remaining width, truncates with ellipsis */}
        <Typography
          variant="body2"
          noWrap
          title={message}
          sx={{ flexGrow: 1, minWidth: 0, fontWeight: 500 }}
        >
          {message}
        </Typography>
      </Stack>

      {/* Row 2: date · origin contact · actions (pushed right) */}
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
  ]).isRequired,
  onSelect: PropTypes.func,
};
