// frontend/src/sections/activities/signals/SignalsGroupedView.jsx

"use client";

import PropTypes from "prop-types";
import { useMemo } from "react";

// MUI
import Box from "@mui/material/Box";
import Grid from "@mui/material/Grid";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import {
  StopOutlined,
  ThunderboltOutlined,
  ToolOutlined,
} from "@ant-design/icons";

// Project imports
import SignalThemeBlock from "./SignalThemeBlock";
import BlockerCompactCard from "./BlockerCompactCard";
import SignalCompactLine from "./SignalCompactLine";

function buildThemeKey(signal) {
  const w = signal.what || "unknown";
  const d = signal.dimension || "unknown";
  return `${w}:${d}`;
}

function buildThemeLabel(signal) {
  const w = signal.what_display || signal.what || "Unknown";
  const d = signal.dimension_display || signal.dimension || "Unknown";
  return `${w} × ${d}`;
}

// ==============================|| SIGNALS GROUPED VIEW ||============================== //

export default function SignalsGroupedView({
  qualificationSignals,
  techStackSignals,
  blockerSignals,
  onSelect,
  onValidate,
  onReject,
  isLocked,
}) {
  const themes = useMemo(() => {
    const map = new Map();
    for (const signal of qualificationSignals) {
      const key = buildThemeKey(signal);
      if (!map.has(key)) {
        map.set(key, {
          key,
          label: buildThemeLabel(signal),
          signals: [],
        });
      }
      map.get(key).signals.push(signal);
    }
    return Array.from(map.values());
  }, [qualificationSignals]);

  const hasQualification = themes.length > 0;
  const hasBlockers = blockerSignals.length > 0;
  const hasTechStack = techStackSignals.length > 0;
  const isEmpty = !hasQualification && !hasBlockers && !hasTechStack;

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
      {/* Left column — Qualification */}
      <Grid item xs={12} md={6}>
        <Typography
          variant="overline"
          color="text.secondary"
          sx={{ mb: 1.5, display: "block", letterSpacing: 1.5 }}
        >
          Qualification
        </Typography>
        {hasQualification ? (
          themes.map((theme) => (
            <SignalThemeBlock
              key={theme.key}
              themeKey={theme.key}
              themeLabel={theme.label}
              signals={theme.signals}
              onSelect={onSelect}
              onValidate={onValidate}
              onReject={onReject}
              isLocked={isLocked}
            />
          ))
        ) : (
          <EmptyZone text="No qualification signals extracted yet" />
        )}
      </Grid>

      {/* Right column — Blockers + TechStack stacked */}
      <Grid item xs={12} md={6}>
        {/* Blockers section */}
        <Stack
          direction="row"
          spacing={1}
          alignItems="center"
          sx={{ mb: 1.5 }}
        >
          <StopOutlined style={{ fontSize: 16, color: "#8c8c8c" }} />
          <Typography
            variant="overline"
            color="text.secondary"
            sx={{ letterSpacing: 1.5 }}
          >
            Blockers / Objections
          </Typography>
        </Stack>
        {hasBlockers ? (
          blockerSignals.map((signal) => (
            <BlockerCompactCard
              key={signal.id}
              signal={signal}
              onSelect={onSelect}
              onValidate={onValidate}
              onReject={onReject}
              isLocked={isLocked}
            />
          ))
        ) : (
          <EmptyZone text="No blockers identified" />
        )}

        {/* TechStack section */}
        <Stack
          direction="row"
          spacing={1}
          alignItems="center"
          sx={{ mt: 3, mb: 1.5 }}
        >
          <ToolOutlined style={{ fontSize: 16, color: "#8c8c8c" }} />
          <Typography
            variant="overline"
            color="text.secondary"
            sx={{ letterSpacing: 1.5 }}
          >
            Tech Stack
          </Typography>
        </Stack>
        {hasTechStack ? (
          <Stack spacing={0}>
            {techStackSignals.map((signal) => (
              <SignalCompactLine
                key={signal.id}
                signal={signal}
                signalType="tech-stack"
                onSelect={onSelect}
                onValidate={onValidate}
                onReject={onReject}
                isLocked={isLocked}
              />
            ))}
          </Stack>
        ) : (
          <EmptyZone text="No tools detected" />
        )}
      </Grid>
    </Grid>
  );
}

function EmptyZone({ text }) {
  return (
    <Box
      sx={{
        py: 3,
        px: 2,
        textAlign: "center",
        bgcolor: "grey.50",
        borderRadius: 1,
        mb: 1.5,
      }}
    >
      <Typography variant="body2" color="text.secondary">
        {text}
      </Typography>
    </Box>
  );
}

EmptyZone.propTypes = {
  text: PropTypes.string.isRequired,
};

SignalsGroupedView.propTypes = {
  qualificationSignals: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      _signalType: PropTypes.string.isRequired,
      what: PropTypes.string,
      what_display: PropTypes.string,
      dimension: PropTypes.string,
      dimension_display: PropTypes.string,
    }),
  ).isRequired,
  techStackSignals: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
    }),
  ).isRequired,
  blockerSignals: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
    }),
  ).isRequired,
  onSelect: PropTypes.func,
  onValidate: PropTypes.func,
  onReject: PropTypes.func,
  isLocked: PropTypes.bool,
};
