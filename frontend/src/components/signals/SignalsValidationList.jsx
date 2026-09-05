// frontend/src/components/signals/SignalsValidationList.jsx
//
// SIG-2 — the flat signal VALIDATION list. One flat list split into 3 stacked
// STATUS sections (To validate / Validated / Rejected); inside each section the
// signals are grouped BY TYPE behind a coloured SignalTypeHeader (SIG-1), and
// each signal is a compact SignalLine. The type is carried ONCE by the group
// header, so the rows render with no type pill (showTypeChip=false). Clicking a
// row calls onSelect so the parent opens the signal drawer (the detail surface).
//
// Generic / reusable on purpose: today it is wired only on the Activity Signals
// tab, but DC and Account will reuse it for their own flat views once they
// migrate off the current shared SignalsFlatView (tracked as tech debt).
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
import SignalLine from "components/signals/SignalLine";
import SignalTypeHeader from "components/signals/SignalTypeHeader";

// The 3 status sections, stacked in this order.
const STATUS_SECTIONS = [
  {
    status: "PENDING",
    title: "To validate",
    testid: "signal-section-to-validate",
    emptyText: "Nothing to validate",
    alwaysShow: true,
  },
  { status: "VALIDATED", title: "Validated", testid: "signal-section-validated" },
  { status: "REJECTED", title: "Rejected", testid: "signal-section-rejected" },
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

// ==============================|| SIGNAL TYPE GROUP ||============================== //

function TypeGroup({ type, signals, onSelect }) {
  return (
    <Box sx={{ mb: 2 }}>
      <Box sx={{ mb: 0.5 }}>
        <SignalTypeHeader signalType={type} data-testid="signal-type-header" />
      </Box>
      {signals.map((signal) => (
        <SignalLine
          key={signal.id}
          signal={signal}
          signalType={type}
          onSelect={onSelect}
          showTypeChip={false}
        />
      ))}
    </Box>
  );
}

TypeGroup.propTypes = {
  type: PropTypes.string.isRequired,
  signals: PropTypes.arrayOf(PropTypes.object).isRequired,
  onSelect: PropTypes.func,
};

// ==============================|| SIGNALS VALIDATION LIST ||============================== //

export default function SignalsValidationList({
  signals,
  onSelect,
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
    <Box>
      {STATUS_SECTIONS.map(({ status, title, testid, emptyText, alwaysShow }) => {
        const sectionSignals = byStatus[status] ?? [];
        // Hide an empty section, except the always-on "To validate".
        if (!sectionSignals.length && !alwaysShow) return null;

        return (
          <Box key={status} data-testid={testid} sx={{ mb: 3 }}>
            <Typography
              data-testid="signal-section-title"
              variant="overline"
              color="text.secondary"
              sx={{ display: "block", fontWeight: 600, mb: 1 }}
            >
              {title}
            </Typography>

            {sectionSignals.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ py: 0.5 }}>
                {emptyText}
              </Typography>
            ) : (
              groupByType(sectionSignals).map(([type, typeSignals]) => (
                <TypeGroup
                  key={type}
                  type={type}
                  signals={typeSignals}
                  onSelect={onSelect}
                />
              ))
            )}
          </Box>
        );
      })}
    </Box>
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
  loading: PropTypes.bool,
  emptyMessage: PropTypes.string,
};
