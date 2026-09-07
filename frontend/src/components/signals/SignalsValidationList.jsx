// frontend/src/components/signals/SignalsValidationList.jsx
//
// SIG-2 / SIG-2-fix* — the flat signal VALIDATION list.
//
// One flat list split into 3 stacked STATUS sections (To validate / Validated /
// Rejected), each a collapsible strip (CollapsibleStrip) with a STATUS-coloured
// title (warning / success / error). Inside a section the signals are grouped BY
// TYPE; a type group is a PLAIN header (uniform muted tone — the SIG-1 per-type
// colours stay in reserve) followed by its rows. Collapse happens ONLY at the
// status-section level (one fold), not per type. Each signal is a compact
// SignalLine carrying NO chips (type / scope / nature / status / contact overflow
// all off) — just its message + muted meta (date · contact · scope). All detail
// lives in the drawer, opened by clicking a row (onSelect).
//
// Default open state: "To validate" is open; "Validated" and "Rejected" start
// collapsed. The section chevron expands / collapses.
//
// Generic / reusable: wired only on the Activity Signals tab today; DC and
// Account will reuse it when they migrate off the shared SignalsFlatView (TD-235).
//
// Lifecycle actions (validate / reject inline) are NOT here — that is SIG-3.

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import { ThunderboltOutlined } from "@ant-design/icons";

// Project imports
import CollapsibleStrip from "components/display/CollapsibleStrip";
import SignalLine from "components/signals/SignalLine";
// Only the type LABEL is used here; the SIG-1 per-type colours (getSignalTypeColor /
// aphoriQ.signalColors) stay in reserve — type headers are a uniform muted tone.
import { getSignalTypeLabel } from "utils/signalTypes";

// The 3 status sections, stacked in this order. `titleColor` is a palette path
// (resolved by MUI sx): a semantic STATUS colour, distinct from the (reserved)
// SIG-1 TYPE colours. To validate = warning, Validated = success, Rejected =
// error (PO: red-for-status is fine in this worklist context).
const STATUS_SECTIONS = [
  {
    status: "PENDING",
    title: "To validate",
    titleColor: "warning.main",
    emptyText: "Nothing to validate",
    defaultExpanded: true,
  },
  {
    status: "VALIDATED",
    title: "Validated",
    titleColor: "success.main",
    defaultExpanded: false,
  },
  {
    status: "REJECTED",
    title: "Rejected",
    titleColor: "error.main",
    defaultExpanded: false,
  },
];

// Stable type order inside every section (PO-validated). Types not listed sort
// last, in insertion order.
const TYPE_ORDER = [
  "objective",
  "pain",
  "impact",
  "constraints",
  "blockers",
  "people",
  "tech-stack",
  "competitors",
  "next-steps",
];

function typeRank(type) {
  const i = TYPE_ORDER.indexOf(type);
  return i === -1 ? TYPE_ORDER.length : i;
}

// Group a section's signals by type, ordered by TYPE_ORDER; row order WITHIN a
// type group is preserved (the caller pre-sorts, e.g. by date via the endpoint).
function groupByType(signals) {
  const byType = new Map();
  signals.forEach((s) => {
    const type = s._signalType;
    if (!byType.has(type)) byType.set(type, []);
    byType.get(type).push(s);
  });
  return [...byType.entries()].sort((a, b) => typeRank(a[0]) - typeRank(b[0]));
}

// ==============================|| SIGNALS VALIDATION LIST ||============================== //

export default function SignalsValidationList({
  signals,
  onSelect,
  onValidate,
  onReject,
  loading = false,
  emptyMessage = "No signals found for this activity",
}) {
  // Loading with nothing to show yet → spinner.
  if (loading && !signals.length) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
        <CircularProgress size={28} />
      </Box>
    );
  }

  // Business-empty is information, not an error (neutral tone).
  if (!signals.length) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="200px"
      >
        <Stack spacing={1} alignItems="center" textAlign="center">
          <ThunderboltOutlined style={{ fontSize: 36, color: "#8c8c8c" }} />
          <Typography variant="body2" color="text.secondary">
            {emptyMessage}
          </Typography>
        </Stack>
      </Box>
    );
  }

  // Bucket by status once.
  const byStatus = { PENDING: [], VALIDATED: [], REJECTED: [] };
  signals.forEach((s) => {
    if (byStatus[s.status]) byStatus[s.status].push(s);
  });

  return (
    <Stack spacing={1.5}>
      {STATUS_SECTIONS.map(
        ({ status, title, titleColor, emptyText, defaultExpanded }) => {
          const sectionSignals = byStatus[status] ?? [];
          const alwaysShow = status === "PENDING";
          // Hide an empty section, except the always-on "To validate".
          if (!sectionSignals.length && !alwaysShow) return null;

          return (
            <CollapsibleStrip
              key={status}
              title={title}
              titleColor={titleColor}
              defaultExpanded={defaultExpanded}
              meta={
                sectionSignals.length ? (
                  // The count takes the section's status colour (not muted).
                  <Box component="span" sx={{ color: titleColor, fontWeight: 600 }}>
                    {sectionSignals.length}
                  </Box>
                ) : undefined
              }
            >
              {sectionSignals.length === 0 ? (
                <Typography variant="body2" color="text.secondary" sx={{ py: 0.5 }}>
                  {emptyText}
                </Typography>
              ) : (
                <Stack spacing={2}>
                  {groupByType(sectionSignals).map(([type, typeSignals]) => (
                    <Box key={type}>
                      {/* Type group = a plain muted header (uniform tone, NOT a
                          per-type colour) + its rows. No nested collapse — the
                          only fold is at the status-section level above. */}
                      <Typography
                        variant="subtitle2"
                        color="text.secondary"
                        sx={{ fontWeight: 500, mb: 0.75 }}
                      >
                        {getSignalTypeLabel(type) ?? type}
                      </Typography>
                      {typeSignals.map((signal) => (
                        <SignalLine
                          key={signal.id}
                          signal={signal}
                          signalType={type}
                          onSelect={onSelect}
                          onValidate={onValidate}
                          onReject={onReject}
                          showTypeChip={false}
                          showScopeChip={false}
                          showNatureChip={false}
                          showStatusChip={false}
                          showContactOverflow={false}
                        />
                      ))}
                    </Box>
                  ))}
                </Stack>
              )}
            </CollapsibleStrip>
          );
        },
      )}
    </Stack>
  );
}

SignalsValidationList.propTypes = {
  /** Signals tagged with `_signalType` and carrying `status` + `id`. */
  signals: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      status: PropTypes.string.isRequired,
      _signalType: PropTypes.string.isRequired,
    }),
  ).isRequired,
  /** (signal, signalType) => void — the parent opens the signal drawer. */
  onSelect: PropTypes.func,
  /** Inline validate on a pending row — (signal, signalType) => Promise. */
  onValidate: PropTypes.func,
  /** Inline reject on a pending row — (signal, signalType) => Promise. */
  onReject: PropTypes.func,
  loading: PropTypes.bool,
  emptyMessage: PropTypes.string,
};
