// frontend/src/sections/accounts/dc-workspace/ThemesView.jsx

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo } from "react";

// MUI
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Grid from "@mui/material/Grid";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import { InboxOutlined } from "@ant-design/icons";

// Project imports
import useDCAllSignals from "hooks/useDCAllSignals";
import { validateSignal, rejectSignal } from "api/signals/signals";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// Activity signal components — reused for inline rendering
import SignalThemeBlock from "sections/activities/signals/SignalThemeBlock";
import SignalCompactLine from "sections/activities/signals/SignalCompactLine";
import BlockerCompactCard from "sections/activities/signals/BlockerCompactCard";

// ==============================|| HELPERS ||============================== //

function buildThemeKey(signal) {
  return `${signal.what || ""}:${signal.dimension || ""}`;
}

function buildThemeLabel(signal) {
  const w = signal.what_display || signal.what || "—";
  const d = signal.dimension_display || signal.dimension || "—";
  return `${w} × ${d}`;
}

function buildThemes(signals) {
  const map = new Map();
  for (const s of signals) {
    const key = buildThemeKey(s);
    if (!map.has(key)) {
      map.set(key, { key, label: buildThemeLabel(s), signals: [] });
    }
    map.get(key).signals.push(s);
  }
  return Array.from(map.values());
}

// ==============================|| EMPTY ZONE ||============================== //

function EmptyZone({ label }) {
  return (
    <Box
      display="flex"
      justifyContent="center"
      alignItems="center"
      sx={{
        py: 3,
        border: 1,
        borderColor: "divider",
        borderRadius: 1.5,
        borderStyle: "dashed",
      }}
    >
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
    </Box>
  );
}

EmptyZone.propTypes = {
  label: PropTypes.string.isRequired,
};

// ==============================|| SECTION HEADER ||============================== //

function SectionHeader({ title, count }) {
  return (
    <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1.5 }}>
      {title}
      {count > 0 && (
        <Typography
          component="span"
          variant="caption"
          color="text.secondary"
          sx={{ ml: 1 }}
        >
          ({count})
        </Typography>
      )}
    </Typography>
  );
}

SectionHeader.propTypes = {
  title: PropTypes.string.isRequired,
  count: PropTypes.number,
};

// ==============================|| THEMES VIEW ||============================== //

export default function ThemesView({ cycleId, accountId }) {
  const {
    qualificationSignals,
    techStackSignals,
    blockerSignals,
    constraintSignals,
    loading,
    error,
    mutateAll,
  } = useDCAllSignals(accountId, cycleId);

  // Handlers
  const handleValidate = useCallback(
    async (signal, signalType) => {
      const result = await validateSignal(signalType, signal.id);
      if (result.success) {
        displaySuccessSnackbar("Signal validated");
        mutateAll();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll],
  );

  const handleReject = useCallback(
    async (signal, signalType) => {
      const result = await rejectSignal(signalType, signal.id);
      if (result.success) {
        displaySuccessSnackbar("Signal rejected");
        mutateAll();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll],
  );

  // Group qualification signals by what × dimension
  const themes = useMemo(
    () => buildThemes(qualificationSignals),
    [qualificationSignals],
  );

  // Loading
  if (loading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="200px"
      >
        <CircularProgress />
      </Box>
    );
  }

  // Error
  if (error) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="200px"
      >
        <Typography color="error">Failed to load signals</Typography>
      </Box>
    );
  }

  // All empty
  const totalCount =
    qualificationSignals.length +
    blockerSignals.length +
    techStackSignals.length +
    constraintSignals.length;

  if (totalCount === 0) {
    return (
      <Box
        display="flex"
        flexDirection="column"
        justifyContent="center"
        alignItems="center"
        minHeight="200px"
        gap={1}
      >
        <InboxOutlined style={{ fontSize: 36, color: "#8c8c8c" }} />
        <Typography color="text.secondary">
          No signals captured for this cycle yet.
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Signals are extracted from activity transcripts or created manually.
        </Typography>
      </Box>
    );
  }

  return (
    <Grid container spacing={3}>
      {/* Left column — Qualification (clusters) */}
      <Grid item xs={12} md={6}>
        <SectionHeader title="Qualification" count={qualificationSignals.length} />
        {themes.length === 0 ? (
          <EmptyZone label="No qualification signals yet" />
        ) : (
          <Stack spacing={1.5}>
            {themes.map((theme) => (
              <SignalThemeBlock
                key={theme.key}
                themeKey={theme.key}
                themeLabel={theme.label}
                signals={theme.signals}
                onValidate={handleValidate}
                onReject={handleReject}
                isLocked={false}
              />
            ))}
          </Stack>
        )}
      </Grid>

      {/* Right column — Flat sections */}
      <Grid item xs={12} md={6}>
        {/* Blockers / Objections */}
        <SectionHeader title="Blockers / Objections" count={blockerSignals.length} />
        {blockerSignals.length === 0 ? (
          <EmptyZone label="No blockers or objections captured" />
        ) : (
          <Stack spacing={1}>
            {blockerSignals.map((s) => (
              <BlockerCompactCard
                key={s.id}
                signal={s}
                onValidate={handleValidate}
                onReject={handleReject}
                isLocked={false}
              />
            ))}
          </Stack>
        )}

        {/* Tech Stack */}
        <Box sx={{ mt: 3 }}>
          <SectionHeader title="Tech Stack" count={techStackSignals.length} />
          {techStackSignals.length === 0 ? (
            <EmptyZone label="No tech stack signals captured" />
          ) : (
            <Stack spacing={0.5}>
              {techStackSignals.map((s) => (
                <SignalCompactLine
                  key={s.id}
                  signal={s}
                  signalType={s._signalType}
                  onValidate={handleValidate}
                  onReject={handleReject}
                  isLocked={false}
                />
              ))}
            </Stack>
          )}
        </Box>

        {/* Constraints */}
        <Box sx={{ mt: 3 }}>
          <SectionHeader title="Constraints" count={constraintSignals.length} />
          {constraintSignals.length === 0 ? (
            <EmptyZone label="No constraints captured" />
          ) : (
            <Stack spacing={0.5}>
              {constraintSignals.map((s) => (
                <SignalCompactLine
                  key={s.id}
                  signal={s}
                  signalType={s._signalType}
                  onValidate={handleValidate}
                  onReject={handleReject}
                  isLocked={false}
                />
              ))}
            </Stack>
          )}
        </Box>
      </Grid>
    </Grid>
  );
}

ThemesView.propTypes = {
  cycleId: PropTypes.string.isRequired,
  accountId: PropTypes.string.isRequired,
};
