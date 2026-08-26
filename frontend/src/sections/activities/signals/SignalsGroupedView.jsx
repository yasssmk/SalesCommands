// frontend/src/sections/activities/signals/SignalsGroupedView.jsx
//
// Activity "Qualification" grouped view.
//
// An activity is a single provenance point, so clustering (which groups
// repetitions ACROSS activities) makes no sense here. This view therefore
// groups signals by TYPE only and renders each type as a FLAT list — no
// cluster cards, no domain×dimension accordion. Domain × dimension, scope,
// quote and contact live in the signal drawer (opened by clicking a row).
//
// Sections:
//   Left column  — Objectives / Pains / Impacts (the qualification types)
//   Right column — Tech Stack / Objections (blockers)
//
// The two-column container is the shared reference layout; only the inner
// grouping changed from (theme / cluster) to (type-section / flat list).
// Rows are the informational SignalLine (status + message + meta); clicking a
// row calls onSelect and the parent opens the drawer where the actions live.

"use client";

import PropTypes from "prop-types";
import { useMemo } from "react";

// MUI
import Box from "@mui/material/Box";
import Grid from "@mui/material/Grid";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import { ThunderboltOutlined } from "@ant-design/icons";

// Project imports
import SignalLine from "components/signals/SignalLine";

// ==============================|| SECTION ||============================== //

/**
 * One type section: an uppercase header with a count, then a flat list of
 * that type's signals as informational SignalLine rows. An empty section is
 * neutral information ("None yet"), never an error surface.
 */
function TypeSection({ title, signalType, signals, onSelect, emptyLabel }) {
  return (
    <Box sx={{ mb: 3 }}>
      <Typography
        variant="overline"
        color="text.secondary"
        sx={{ mb: 1, display: "block", letterSpacing: 1.5 }}
      >
        {title}
        <Typography
          component="span"
          variant="caption"
          color="text.disabled"
          sx={{ ml: 1, letterSpacing: 0 }}
        >
          ({signals.length})
        </Typography>
      </Typography>

      {signals.length === 0 ? (
        <Box
          sx={{
            py: 2.5,
            px: 2,
            textAlign: "center",
            border: 1,
            borderColor: "divider",
            borderStyle: "dashed",
            borderRadius: 1.5,
          }}
        >
          <Typography variant="caption" color="text.secondary">
            {emptyLabel}
          </Typography>
        </Box>
      ) : (
        <Stack spacing={0}>
          {signals.map((signal) => (
            <SignalLine
              key={signal.id}
              signal={signal}
              signalType={signal._signalType || signalType}
              onSelect={onSelect}
              showTypeChip={false}
            />
          ))}
        </Stack>
      )}
    </Box>
  );
}

TypeSection.propTypes = {
  title: PropTypes.string.isRequired,
  signalType: PropTypes.string.isRequired,
  signals: PropTypes.array.isRequired,
  onSelect: PropTypes.func,
  emptyLabel: PropTypes.string.isRequired,
};

// ==============================|| SIGNALS GROUPED VIEW (ACTIVITY) ||============================== //

export default function SignalsGroupedView({
  qualificationSignals,
  techStackSignals,
  blockerSignals,
  onSelect,
}) {
  // Split the mixed qualification list into its three types. Each signal is
  // tagged with _signalType by the activity hook.
  const objectives = useMemo(
    () => qualificationSignals.filter((s) => s._signalType === "objective"),
    [qualificationSignals],
  );
  const pains = useMemo(
    () => qualificationSignals.filter((s) => s._signalType === "pain"),
    [qualificationSignals],
  );
  const impacts = useMemo(
    () => qualificationSignals.filter((s) => s._signalType === "impact"),
    [qualificationSignals],
  );

  const isEmpty =
    qualificationSignals.length === 0 &&
    techStackSignals.length === 0 &&
    blockerSignals.length === 0;

  if (isEmpty) {
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
            No signals found for this activity
          </Typography>
        </Stack>
      </Box>
    );
  }

  return (
    <Grid container spacing={3}>
      {/* Left column — qualification types */}
      <Grid item xs={12} md={6}>
        <TypeSection
          title="Objectives"
          signalType="objective"
          signals={objectives}
          onSelect={onSelect}
          emptyLabel="No objectives extracted yet"
        />
        <TypeSection
          title="Pains"
          signalType="pain"
          signals={pains}
          onSelect={onSelect}
          emptyLabel="No pains extracted yet"
        />
        <TypeSection
          title="Impacts"
          signalType="impact"
          signals={impacts}
          onSelect={onSelect}
          emptyLabel="No impacts extracted yet"
        />
      </Grid>

      {/* Right column — tech stack + objections */}
      <Grid item xs={12} md={6}>
        <TypeSection
          title="Tech Stack"
          signalType="tech-stack"
          signals={techStackSignals}
          onSelect={onSelect}
          emptyLabel="No tools detected"
        />
        <TypeSection
          title="Objections"
          signalType="blockers"
          signals={blockerSignals}
          onSelect={onSelect}
          emptyLabel="No objections identified"
        />
      </Grid>
    </Grid>
  );
}

SignalsGroupedView.propTypes = {
  /** pain + objective + impact, each tagged with _signalType. */
  qualificationSignals: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      _signalType: PropTypes.string.isRequired,
    }),
  ).isRequired,
  techStackSignals: PropTypes.arrayOf(
    PropTypes.shape({ id: PropTypes.string.isRequired }),
  ).isRequired,
  blockerSignals: PropTypes.arrayOf(
    PropTypes.shape({ id: PropTypes.string.isRequired }),
  ).isRequired,
  onSelect: PropTypes.func,
};
