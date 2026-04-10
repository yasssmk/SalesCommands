// frontend/src/sections/accounts/signals/wizard/WizardSummary.jsx
/**
 * WizardSummary — recap screen for the WizardSignalAdd drawer.
 *
 * Replaces the section view entirely once the user clicks "Review & Save".
 *
 * Responsibilities:
 *   - Show all staged signals grouped by type
 *   - Allow last-minute VALIDATED / REJECTED toggle per signal
 *   - Show dispatch errors inline on failed signals (post-confirm)
 *   - Expose [Back] and [Confirm] actions
 *
 * Signals with _status === 'REJECTED' are excluded from dispatch.
 * The Confirm button shows the count of signals that will actually be sent.
 *
 * results prop is set after a partial-failure dispatch:
 *   { succeeded: [{ _key, type }], failed: [{ _key, type, error }] }
 * Failed signals are highlighted with their error message.
 */

"use client";

import PropTypes from "prop-types";
import { useMemo } from "react";

// material-ui
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// ant-design icons
import ArrowLeftOutlined from "@ant-design/icons/ArrowLeftOutlined";
import CheckCircleOutlined from "@ant-design/icons/CheckCircleOutlined";
import CloseCircleOutlined from "@ant-design/icons/CloseCircleOutlined";
import SendOutlined from "@ant-design/icons/SendOutlined";

// ==============================|| CONSTANTS ||============================== //

const TYPE_CONFIG = {
  people: { label: "People", color: "secondary" },
  pain: { label: "Pain", color: "error" },
  objective: { label: "Objective", color: "info" },
  "tech-stack": { label: "Tech Stack", color: "primary" },
};

/** Ordered for display in the summary */
const TYPE_ORDER = ["pain", "objective", "people", "tech-stack"];

// ==============================|| HELPERS ||============================== //

/**
 * Resolve a display label from a choices array by value.
 */
function resolveLabel(options, value) {
  if (!value || !options) return value ?? null;
  return options.find((o) => o.value === value)?.label ?? value;
}

/**
 * Derive a short human-readable primary label for a staged signal.
 *
 * @param {'people'|'pain'|'objective'|'tech-stack'} type
 * @param {Object} signal
 * @param {Object} choices
 * @returns {string}
 */
function getPrimaryLabel(type, signal, choices) {
  switch (type) {
    case "pain":
    case "objective":
      return signal.summary
        ? signal.summary.slice(0, 80) + (signal.summary.length > 80 ? "…" : "")
        : "—";
    case "people":
      return resolveLabel(choices?.people_roles, signal.role) ?? "—";
    case "tech-stack":
      return signal.tech_name || "Unnamed tool";
    default:
      return "—";
  }
}

// ==============================|| SUMMARY SIGNAL CARD ||============================== //

/**
 * SummarySignalCard — compact card for a single staged signal in the recap.
 *
 * Shows: type chip · primary label · toggle button
 * If the signal failed dispatch, shows an error alert below.
 */
function SummarySignalCard({
  type,
  signal,
  choices,
  onToggleStatus,
  failureError,
}) {
  const isRejected = signal._status === "REJECTED";
  const typeCfg = TYPE_CONFIG[type] ?? { label: type, color: "default" };
  const primaryLabel = getPrimaryLabel(type, signal, choices);

  return (
    <Box
      sx={{
        border: "1px solid",
        borderColor: failureError
          ? "error.main"
          : isRejected
            ? "divider"
            : `${typeCfg.color}.light`,
        borderRadius: 1.5,
        p: 1.5,
        bgcolor: isRejected ? "action.hover" : "background.paper",
        opacity: isRejected ? 0.65 : 1,
        transition: "border-color 0.15s, opacity 0.15s",
      }}
    >
      <Stack spacing={1}>
        <Stack direction="row" spacing={1} alignItems="center">
          {/* Type chip */}
          <Chip
            label={typeCfg.label}
            color={isRejected ? "default" : typeCfg.color}
            size="small"
            variant="outlined"
            sx={{ fontSize: "0.62rem", height: 18, flexShrink: 0 }}
          />

          {/* Primary label */}
          <Typography
            variant="body2"
            flex={1}
            sx={{
              textDecoration: isRejected ? "line-through" : "none",
              color: isRejected ? "text.disabled" : "text.primary",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {primaryLabel}
          </Typography>

          {/* Toggle button */}
          <Button
            size="small"
            variant={isRejected ? "outlined" : "contained"}
            color={isRejected ? "error" : typeCfg.color}
            onClick={() => onToggleStatus(type, signal._key)}
            startIcon={
              isRejected ? (
                <CloseCircleOutlined style={{ fontSize: 12 }} />
              ) : (
                <CheckCircleOutlined style={{ fontSize: 12 }} />
              )
            }
            sx={{ flexShrink: 0, fontSize: "0.68rem", px: 1, py: 0.25 }}
          >
            {isRejected ? "Excluded" : "Include"}
          </Button>
        </Stack>

        {/* Dispatch failure error */}
        {failureError && (
          <Alert severity="error" sx={{ py: 0.25, fontSize: "0.75rem" }}>
            {failureError}
          </Alert>
        )}
      </Stack>
    </Box>
  );
}

SummarySignalCard.propTypes = {
  type: PropTypes.oneOf(["people", "pain", "objective", "tech-stack"])
    .isRequired,
  signal: PropTypes.shape({
    _key: PropTypes.string.isRequired,
    _status: PropTypes.oneOf(["VALIDATED", "REJECTED"]).isRequired,
  }).isRequired,
  choices: PropTypes.object,
  onToggleStatus: PropTypes.func.isRequired,
  failureError: PropTypes.string,
};

// ==============================|| WIZARD SUMMARY ||============================== //

/**
 * WizardSummary
 *
 * @param {Object}   staged          - { people, pain, objective, 'tech-stack' } arrays
 * @param {Function} onToggleStatus  - (type, _key) => void
 * @param {Function} onBack          - () => void — return to section view
 * @param {Function} onConfirm       - () => void — trigger dispatch
 * @param {boolean}  submitting      - True while dispatch is in progress
 * @param {Object}   results         - null before dispatch, { succeeded, failed } after partial failure
 * @param {Object}   choices         - From useGetSignalChoices()
 */
export default function WizardSummary({
  staged,
  onToggleStatus,
  onBack,
  onConfirm,
  submitting,
  results,
  choices,
}) {
  // ==============================|| DERIVED ||============================== //

  /** Flat list of all signals across all types with their type tag */
  const allSignals = useMemo(
    () =>
      TYPE_ORDER.flatMap((type) =>
        (staged[type] ?? []).map((s) => ({ ...s, _type: type })),
      ),
    [staged],
  );

  /** Count of signals that will be dispatched (VALIDATED only) */
  const willSendCount = useMemo(
    () => allSignals.filter((s) => s._status === "VALIDATED").length,
    [allSignals],
  );

  /** Total staged count regardless of status */
  const totalCount = allSignals.length;

  /**
   * Build a lookup map for dispatch failures:
   *   { [_key]: errorMessage }
   */
  const failureMap = useMemo(() => {
    if (!results?.failed?.length) return {};
    return Object.fromEntries(
      results.failed.map((f) => [f._key, f.error ?? "Failed to create signal"]),
    );
  }, [results]);

  /** True if the last dispatch had at least one failure */
  const hasFailures = Boolean(results?.failed?.length);

  // ==============================|| RENDER ||============================== //

  return (
    <Stack
      spacing={0}
      sx={{ height: "100%", display: "flex", flexDirection: "column" }}
    >
      {/* ---- Header ---- */}
      <Box sx={{ px: 3, pt: 2.5, pb: 2 }}>
        <Typography variant="h6" fontWeight={600}>
          Review Signals
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          {totalCount === 0
            ? "No signals staged yet."
            : willSendCount === 0
              ? "All signals are excluded — re-include at least one to save."
              : `${willSendCount} of ${totalCount} signal${totalCount === 1 ? "" : "s"} will be created. Toggle to exclude any.`}
        </Typography>
      </Box>

      <Divider />

      {/* ---- Partial failure banner ---- */}
      {hasFailures && (
        <Box sx={{ px: 3, pt: 2 }}>
          <Alert severity="warning">
            {results.failed.length} signal
            {results.failed.length === 1 ? "" : "s"} failed to save. Review the
            errors below, then confirm again to retry.
          </Alert>
        </Box>
      )}

      {/* ---- Signal list grouped by type ---- */}
      <Box sx={{ flex: 1, overflowY: "auto", px: 3, py: 2 }}>
        {totalCount === 0 ? (
          <Typography
            variant="body2"
            color="text.disabled"
            textAlign="center"
            py={6}
          >
            Go back and add signals to each section.
          </Typography>
        ) : (
          <Stack spacing={3}>
            {TYPE_ORDER.map((type) => {
              const signals = staged[type] ?? [];
              if (signals.length === 0) return null;

              const typeCfg = TYPE_CONFIG[type];

              return (
                <Stack key={type} spacing={1}>
                  {/* Section label */}
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Typography
                      variant="caption"
                      fontWeight={600}
                      color="text.secondary"
                    >
                      {typeCfg.label.toUpperCase()}
                    </Typography>
                    <Chip
                      label={
                        signals.filter((s) => s._status === "VALIDATED").length
                      }
                      size="small"
                      color={typeCfg.color}
                      sx={{ height: 16, fontSize: "0.6rem" }}
                    />
                  </Stack>

                  {/* Signal cards for this type */}
                  {signals.map((signal) => (
                    <SummarySignalCard
                      key={signal._key}
                      type={type}
                      signal={signal}
                      choices={choices}
                      onToggleStatus={onToggleStatus}
                      failureError={failureMap[signal._key]}
                    />
                  ))}
                </Stack>
              );
            })}
          </Stack>
        )}
      </Box>

      <Divider />

      {/* ---- Footer actions ---- */}
      <Box sx={{ px: 3, py: 2 }}>
        <Stack
          direction="row"
          spacing={1.5}
          justifyContent="space-between"
          alignItems="center"
        >
          {/* Back */}
          <Button
            size="small"
            color="inherit"
            startIcon={<ArrowLeftOutlined style={{ fontSize: 13 }} />}
            onClick={onBack}
            disabled={submitting}
          >
            Back
          </Button>

          {/* Confirm */}
          <Button
            variant="contained"
            size="small"
            onClick={onConfirm}
            disabled={submitting || willSendCount === 0}
            color={willSendCount === 0 ? "inherit" : "primary"}
            startIcon={
              submitting ? (
                <CircularProgress size={13} color="inherit" />
              ) : (
                <SendOutlined style={{ fontSize: 13 }} />
              )
            }
          >
            {submitting
              ? "Saving…"
              : willSendCount === 0
                ? "Nothing to save"
                : `Save ${willSendCount} Signal${willSendCount === 1 ? "" : "s"}`}
          </Button>
        </Stack>
      </Box>
    </Stack>
  );
}

// ==============================|| PROP TYPES ||============================== //

WizardSummary.propTypes = {
  staged: PropTypes.shape({
    people: PropTypes.array,
    pain: PropTypes.array,
    objective: PropTypes.array,
    "tech-stack": PropTypes.array,
  }).isRequired,
  onToggleStatus: PropTypes.func.isRequired,
  onBack: PropTypes.func.isRequired,
  onConfirm: PropTypes.func.isRequired,
  submitting: PropTypes.bool,
  results: PropTypes.shape({
    succeeded: PropTypes.arrayOf(
      PropTypes.shape({ _key: PropTypes.string, type: PropTypes.string }),
    ),
    failed: PropTypes.arrayOf(
      PropTypes.shape({
        _key: PropTypes.string,
        type: PropTypes.string,
        error: PropTypes.string,
      }),
    ),
  }),
  choices: PropTypes.object,
};
