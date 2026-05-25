// frontend/src/sections/activities/signals/wizard/WizardValidationStep.jsx
/**
 * WizardValidationStep — second step of the signal capture wizard.
 *
 * Renders a recap of all staged signals grouped by type, with last-
 * minute Include / Exclude toggles, edit-back callbacks, and the
 * dispatch confirmation flow.
 *
 * Refactored from the legacy WizardSummary component:
 *   - Renamed to fit the new 2-step wizard naming (Capture →
 *     Validation)
 *   - Removed the redundant "Review Signals" h6 — the wizard's
 *     stepper already labels this step "Validation"
 *   - The Back button now calls onBackClick() so the parent
 *     (WizardSignalAdd) drives the activeStep transition
 *
 * Responsibilities:
 *   - Show all staged signals grouped by type
 *   - Allow last-minute VALIDATED / REJECTED toggle per signal
 *   - Show dispatch errors inline on failed signals (post-confirm)
 *   - Expose [Back] and [Confirm] actions
 *
 * Signals with _status === 'REJECTED' are excluded from dispatch.
 * The Confirm button shows the count of signals that will actually
 * be sent.
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
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// ant-design icons
import ArrowLeftOutlined from "@ant-design/icons/ArrowLeftOutlined";
import CheckCircleOutlined from "@ant-design/icons/CheckCircleOutlined";
import CloseCircleOutlined from "@ant-design/icons/CloseCircleOutlined";
import EditOutlined from "@ant-design/icons/EditOutlined";
import SendOutlined from "@ant-design/icons/SendOutlined";

// ==============================|| CONSTANTS ||============================== //

const TYPE_CONFIG = {
  pain: { label: "Pain", color: "error" },
  objective: { label: "Objective", color: "info" },
  impact: { label: "Impact", color: "secondary" },
  "tech-stack": { label: "Tech Stack", color: "primary" },
};

/** Ordered for display in the validation recap */
const TYPE_ORDER = ["pain", "objective", "impact", "tech-stack"];

// ==============================|| HELPERS ||============================== //

/**
 * Derive a short human-readable primary label for a staged signal.
 *
 * @param {'pain'|'objective'|'impact'|'tech-stack'} type
 * @param {Object} signal
 * @returns {string}
 */
function getPrimaryLabel(type, signal) {
  switch (type) {
    case "pain":
    case "objective":
    case "impact":
      return signal.summary
        ? signal.summary.slice(0, 80) + (signal.summary.length > 80 ? "…" : "")
        : "—";
    case "tech-stack": {
      // TechStack: "Salesforce Sales Cloud" or fallback to Unnamed tool
      const entry = signal.tech_catalog_entry;
      if (!entry) return "Unnamed tool";
      const company = entry.company_name?.trim() || "";
      const product = entry.product_name?.trim() || "";
      if (!company && !product) return "Unnamed tool";
      if (!company) return product;
      if (!product || product === company) return company;
      return `${company} ${product}`;
    }
    default:
      return "—";
  }
}

// ==============================|| VALIDATION SIGNAL CARD ||============================== //

/**
 * ValidationSignalCard — compact card for a single staged signal in
 * the validation recap.
 *
 * Shows: type chip · primary label · edit · toggle button
 * If the signal failed dispatch, shows an error alert below.
 */
function ValidationSignalCard({
  type,
  signal,
  onToggleStatus,
  onEdit,
  failureError,
}) {
  const isRejected = signal._status === "REJECTED";
  const typeCfg = TYPE_CONFIG[type] ?? { label: type, color: "default" };
  const primaryLabel = getPrimaryLabel(type, signal);

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

          {/* Edit button — only when not rejected and no failure */}
          {!isRejected && !failureError && (
            <IconButton
              size="small"
              onClick={() => onEdit(type, signal._key)}
              aria-label="Edit signal"
              sx={{
                flexShrink: 0,
                color: "text.disabled",
                "&:hover": { color: "primary.main" },
              }}
            >
              <EditOutlined style={{ fontSize: 13 }} />
            </IconButton>
          )}

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

ValidationSignalCard.propTypes = {
  type: PropTypes.oneOf(["pain", "objective", "impact", "tech-stack"])
    .isRequired,
  signal: PropTypes.shape({
    _key: PropTypes.string.isRequired,
    _status: PropTypes.oneOf(["VALIDATED", "REJECTED"]).isRequired,
  }).isRequired,
  onToggleStatus: PropTypes.func.isRequired,
  onEdit: PropTypes.func.isRequired,
  failureError: PropTypes.string,
};

// ==============================|| WIZARD VALIDATION STEP ||============================== //

/**
 * WizardValidationStep
 *
 * @param {Object}   staged          - { pain, objective, 'tech-stack' } arrays
 * @param {Function} onToggleStatus  - (type, _key) => void
 * @param {Function} onEdit          - (type, _key) => void — edit-back to Capture
 * @param {Function} onBackClick     - () => void — return to Capture step
 * @param {Function} onConfirm       - () => void — trigger dispatch
 * @param {boolean}  submitting      - True while dispatch is in progress
 * @param {Object}   results         - null before dispatch, { succeeded, failed }
 *                                     after partial failure
 */
export default function WizardValidationStep({
  staged,
  onToggleStatus,
  onEdit,
  onBackClick,
  onConfirm,
  submitting,
  results,
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
    <Stack sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* ---- Header (sub-text only — stepper labels the step) ---- */}
      <Box sx={{ px: 3, pt: 2.5, pb: 2, flexShrink: 0 }}>
        <Typography variant="body2" color="text.secondary">
          {totalCount === 0
            ? "No signals staged yet."
            : willSendCount === 0
              ? "All signals are excluded — re-include at least one to save."
              : `${willSendCount} of ${totalCount} signal${totalCount === 1 ? "" : "s"} will be created. Toggle to exclude any.`}
        </Typography>
      </Box>

      <Divider sx={{ flexShrink: 0 }} />

      {/* ---- Partial failure banner ---- */}
      {hasFailures && (
        <Box sx={{ px: 3, pt: 2, flexShrink: 0 }}>
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
            Go back and add signals from any section.
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
                    <ValidationSignalCard
                      key={signal._key}
                      type={type}
                      signal={signal}
                      onToggleStatus={onToggleStatus}
                      onEdit={onEdit}
                      failureError={failureMap[signal._key]}
                    />
                  ))}
                </Stack>
              );
            })}
          </Stack>
        )}
      </Box>

      <Divider sx={{ flexShrink: 0 }} />

      {/* ---- Footer actions ---- */}
      <Box sx={{ px: 3, py: 2, flexShrink: 0 }}>
        <Stack
          direction="row"
          spacing={1.5}
          justifyContent="space-between"
          alignItems="center"
        >
          {/* Back to Capture step */}
          <Button
            size="small"
            color="inherit"
            startIcon={<ArrowLeftOutlined style={{ fontSize: 13 }} />}
            onClick={onBackClick}
            disabled={submitting}
          >
            Back
          </Button>

          {/* Confirm — triggers dispatch */}
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

WizardValidationStep.propTypes = {
  staged: PropTypes.shape({
    pain: PropTypes.array,
    objective: PropTypes.array,
    impact: PropTypes.array,
    "tech-stack": PropTypes.array,
  }).isRequired,
  onToggleStatus: PropTypes.func.isRequired,
  onEdit: PropTypes.func.isRequired,
  onBackClick: PropTypes.func.isRequired,
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
};
