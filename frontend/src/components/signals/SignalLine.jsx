// frontend/src/components/signals/SignalLine.jsx

"use client";

import PropTypes from "prop-types";
import { useState } from "react";

// MUI
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// Icon size token (the project's iconSizes source — used directly so the row
// needs no theme wrapper). sm = 14px.
import IconSizes from "themes/iconSizes";

// Icons
import {
  UserOutlined,
  CalendarOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  CheckOutlined,
  CloseOutlined,
  StopOutlined,
} from "@ant-design/icons";

// Project imports
import SignalTypeChip from "components/chips/SignalTypeChip";
import ContactInline from "components/signals/ContactInline";
import { getTechSummary } from "sections/activities/signals/utils/signalDisplay";

const ICON_SIZES = IconSizes();

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
      // The person's identity is the row message: full_name first, then the
      // summary/notes fallback. (Refined rendering — role/department chips —
      // is deferred to the UX Activity sprint.)
      return signal.full_name || signal.summary || signal.notes || "—";
    case "competitors":
      // The competitor's identity is its name — NOT the narrative `summary`,
      // which carries a technical "competitor: …" prefix. Matches the drawer,
      // which shows competitor_name.
      return signal.competitor_name || signal.summary || "—";
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

// Truthy when the first contact has a displayable identity — guards the meta
// contact block. The rendering itself is delegated to ContactInline (SIG-5f:
// name bold/primary, job · department muted).
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
  onValidate,
  onReject,
  showTypeChip = true,
  showScopeChip = true,
  showNatureChip = true,
  showStatusChip = true,
  showContactOverflow = true,
}) {
  const isRejected = signal.status === "REJECTED";

  const message = getMessage(signal, signalType);
  const scopeLabel = getScopeLabel(signal, signalType);
  const dateLabel = formatShortDate(signal.created_at);
  const statusConfig = STATUS_LIGHT[signal.status] ?? null;

  const contacts = signal.source_context?.contacts ?? [];
  const originContact = formatOriginContact(contacts[0]);
  const extraContacts = contacts.length > 1 ? contacts.length - 1 : 0;

  // Inline validate / reject — only on a PENDING row, and only when a caller
  // wires the handlers (the Activity validation list). DC/Account pass none →
  // no inline actions (unchanged). "Always clickable" = no missing-field guard;
  // a business error (e.g. incomplete signal → 400) surfaces via the caller's
  // snackbar. `busy` blocks a double-click during the async call.
  const canAct = signal.status === "PENDING" && Boolean(onValidate || onReject);
  const [busy, setBusy] = useState(null); // "validate" | "reject" | null

  const runAction = async (kind, fn, e) => {
    e.stopPropagation(); // never bubble to the row → drawer
    if (busy || !fn) return;
    setBusy(kind);
    try {
      await fn(signal, signalType);
    } finally {
      setBusy(null);
    }
  };

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
        flexDirection: "row",
        alignItems: "center",
        gap: 1,
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
      {/* Content column (message + meta) — flex-grows; actions sit to its right. */}
      <Box sx={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 0.75 }}>
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
            <ContactInline contact={contacts[0]} variant="caption" noWrap />
            {showContactOverflow && extraContacts > 0 && (
              <Chip
                label={`+${extraContacts}`}
                size="small"
                variant="outlined"
                sx={{ height: 18, fontSize: "0.65rem" }}
              />
            )}
          </Stack>
        )}

        {/* Nature — constraint classification axis (Constraint only). Hidden in
            the validation list (showNatureChip=false); detail lives in drawer. */}
        {showNatureChip && signalType === "constraints" && signal.nature_display && (
          <Chip
            label={signal.nature_display}
            size="small"
            variant="outlined"
            sx={{ height: 20, fontSize: "0.68rem", flexShrink: 0 }}
          />
        )}

        {/* Signal scope — an outlined chip on the DC / Account flat views
            (default). The Activity validation list passes showScopeChip=false,
            which drops the signal scope entirely (neither chip nor text — the
            scope/department lives in the drawer). The CONTACT identity above is
            unaffected. */}
        {showScopeChip && scopeLabel && (
          <Chip
            label={scopeLabel}
            size="small"
            variant="outlined"
            sx={{ height: 20, fontSize: "0.68rem", flexShrink: 0 }}
          />
        )}

        {/* Spacer pushes the status to the right edge of the meta line. */}
        <Box sx={{ flexGrow: 1 }} />

        {/* Light status treatment (DS `light` Chip variant + icon). Hidden in
            the validation list (showStatusChip=false): the status section title
            already names it (a row under "To validate" is Pending). */}
        {showStatusChip && statusConfig && (
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

      {/* Inline actions (validation worklist) — ✓ validate / ✗ reject, to the
          right of the row. stopPropagation keeps them from opening the drawer;
          clicking the rest of the row still does. Colours via palette roles
          (success / error), size via the iconSizes token. */}
      {canAct && (
        <Stack
          direction="row"
          spacing={0.25}
          alignItems="center"
          sx={{ flexShrink: 0 }}
          onClick={(e) => e.stopPropagation()}
        >
          <Tooltip title="Validate">
            <span>
              <IconButton
                size="small"
                color="success"
                aria-label="Validate signal"
                disabled={Boolean(busy)}
                onClick={(e) => runAction("validate", onValidate, e)}
              >
                {busy === "validate" ? (
                  <CircularProgress size={ICON_SIZES.sm} color="inherit" />
                ) : (
                  <CheckOutlined style={{ fontSize: ICON_SIZES.sm }} />
                )}
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Reject">
            <span>
              <IconButton
                size="small"
                color="error"
                aria-label="Reject signal"
                disabled={Boolean(busy)}
                onClick={(e) => runAction("reject", onReject, e)}
              >
                {busy === "reject" ? (
                  <CircularProgress size={ICON_SIZES.sm} color="inherit" />
                ) : (
                  <CloseOutlined style={{ fontSize: ICON_SIZES.sm }} />
                )}
              </IconButton>
            </span>
          </Tooltip>
        </Stack>
      )}
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
  /** Inline validate — (signal, type) => Promise. Shown on PENDING rows only. */
  onValidate: PropTypes.func,
  /** Inline reject — (signal, type) => Promise. Shown on PENDING rows only. */
  onReject: PropTypes.func,
  /** Hide the type chip when the surrounding section already names the type. */
  showTypeChip: PropTypes.bool,
  /** Show the signal scope as an outlined chip (default true); false → no scope at all. */
  showScopeChip: PropTypes.bool,
  /** Show the constraint nature chip (default true; false in the validation list). */
  showNatureChip: PropTypes.bool,
  /** Show the status chip (default true; false in the validation list). */
  showStatusChip: PropTypes.bool,
  /** Show the "+N" contact-overflow chip (default true; false in the validation list). */
  showContactOverflow: PropTypes.bool,
};
