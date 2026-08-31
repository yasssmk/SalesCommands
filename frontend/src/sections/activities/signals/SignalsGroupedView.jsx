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
import CollapsibleSection from "components/signals/CollapsibleSection";

// ==============================|| SECTION ||============================== //

/**
 * One collapsible type section (open by default): a header with a count, then
 * a flat list of that type's signals as informational SignalLine rows. An
 * empty section is neutral information ("None yet"), never an error surface.
 */
function TypeSection({ title, signalType, signals, onSelect, emptyLabel }) {
  return (
    <CollapsibleSection
      title={title}
      count={signals.length}
      level="section"
      testId={`section-${signalType}`}
    >
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
    </CollapsibleSection>
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
  constraintSignals = [],
  competitorSignals = [],
  peopleSignals = [],
  onSelect,
}) {
  // No type filter in the grouped view — the structure IS by type section, so
  // every section always renders (mirrors Account/DC grouped). The signals are
  // already filtered client-side by the caller.
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
    blockerSignals.length === 0 &&
    constraintSignals.length === 0 &&
    competitorSignals.length === 0 &&
    peopleSignals.length === 0;

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
      {/* Left column — qualification types (every section always renders). */}
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

      {/* Right column — tech stack + objections. */}
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
        <TypeSection
          title="Constraints"
          signalType="constraints"
          signals={constraintSignals}
          onSelect={onSelect}
          emptyLabel="No constraints identified"
        />
        <TypeSection
          title="Competitors"
          signalType="competitors"
          signals={competitorSignals}
          onSelect={onSelect}
          emptyLabel="No competitors named"
        />
        <TypeSection
          title="People"
          signalType="people"
          signals={peopleSignals}
          onSelect={onSelect}
          emptyLabel="No people identified"
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
  constraintSignals: PropTypes.arrayOf(
    PropTypes.shape({ id: PropTypes.string.isRequired }),
  ),
  competitorSignals: PropTypes.arrayOf(
    PropTypes.shape({ id: PropTypes.string.isRequired }),
  ),
  peopleSignals: PropTypes.arrayOf(
    PropTypes.shape({ id: PropTypes.string.isRequired }),
  ),
  onSelect: PropTypes.func,
};
