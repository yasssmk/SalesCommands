// frontend/src/sections/activities/signals/wizard/WizardStepper.jsx
/**
 * WizardStepper — Apple-style horizontal stepper for the signal capture wizard.
 *
 * Visual model (2 steps):
 *
 *     ●━━━━━━━━━━━━○
 *   Capture     Validation
 *
 * States per step:
 *   completed → filled circle with checkmark, primary color
 *   active    → filled circle with index, primary color + soft outer ring
 *   pending   → outlined circle, divider color, muted label
 *
 * The connector between two steps fills with primary color when the
 * left step is completed, otherwise stays neutral (divider color).
 *
 * Click behaviour
 * ---------------
 * The component does not enforce navigation rules of its own. It calls
 * onStepClick(stepIndex) on every clickable step. The parent decides
 * whether a step is reachable via the `disabledSteps` prop — a typical
 * use is "disable Validation until at least one signal is staged".
 *
 *   - Click on the active step      → no-op
 *   - Click on a disabled step      → no-op (cursor turns not-allowed)
 *   - Click on any other step       → onStepClick(idx)
 *
 * Designed for inline use at the top of a Dialog header — keeps a
 * compact vertical footprint (~56px including labels).
 *
 * Generic by design — works with any number of steps, but the wizard
 * uses exactly 2 (Capture → Validation).
 */

"use client";

import PropTypes from "prop-types";
import { Fragment } from "react";

// material-ui
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { alpha } from "@mui/material/styles";

// ant-design icons
import CheckOutlined from "@ant-design/icons/CheckOutlined";

// ==============================|| CONSTANTS ||============================== //

const CIRCLE_SIZE = 28; // px — circle diameter
const CONNECTOR_HEIGHT = 2; // px — connector line thickness
const TRANSITION = "all 0.2s ease";

// ==============================|| STEP CIRCLE ||============================== //

/**
 * Inner circle visual — driven by `state`. No interactivity here;
 * the parent Stack carries the click handler so the whole step
 * (circle + label) is one click target.
 */
function StepCircle({ index, state }) {
  const isCompleted = state === "completed";
  const isPending = state === "pending";

  return (
    <Box
      sx={{
        width: CIRCLE_SIZE,
        height: CIRCLE_SIZE,
        borderRadius: "50%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
        bgcolor: isPending ? "transparent" : "primary.main",
        border: "2px solid",
        borderColor: isPending ? "divider" : "primary.main",
        color: isPending ? "text.disabled" : "common.white",
        transition: TRANSITION,
        // Soft outer ring on the active step — Apple-ish focus cue
        boxShadow:
          state === "active"
            ? (theme) => `0 0 0 4px ${alpha(theme.palette.primary.main, 0.1)}`
            : "none",
      }}
    >
      {isCompleted ? (
        <CheckOutlined style={{ fontSize: 14 }} />
      ) : (
        <Typography
          variant="caption"
          fontWeight={700}
          sx={{ fontSize: "0.78rem", lineHeight: 1 }}
        >
          {index + 1}
        </Typography>
      )}
    </Box>
  );
}

StepCircle.propTypes = {
  index: PropTypes.number.isRequired,
  state: PropTypes.oneOf(["completed", "active", "pending"]).isRequired,
};

// ==============================|| WIZARD STEPPER ||============================== //

/**
 * WizardStepper
 *
 * @param {Array<{key: string, label: string}>} steps - Ordered step definitions
 * @param {number}   activeStep      - Currently active step index (0-based)
 * @param {Function} onStepClick     - (stepIndex: number) => void
 * @param {Array<number>} [disabledSteps]
 *                                   - Step indices that cannot be navigated to
 *                                     (cursor not-allowed, click no-op).
 *                                     Empty by default — typical use is
 *                                     `[1]` to gate Validation until at
 *                                     least one signal is staged.
 */
export default function WizardStepper({
  steps,
  activeStep,
  onStepClick,
  disabledSteps,
}) {
  const disabledSet = new Set(disabledSteps ?? []);

  const getState = (idx) => {
    if (idx < activeStep) return "completed";
    if (idx === activeStep) return "active";
    return "pending";
  };

  const handleClick = (idx) => {
    if (idx === activeStep) return;
    if (disabledSet.has(idx)) return;
    onStepClick?.(idx);
  };

  return (
    <Stack
      direction="row"
      alignItems="flex-start"
      sx={{ width: "100%", px: 3, py: 1.5 }}
    >
      {steps.map((step, idx) => {
        const state = getState(idx);
        const isDisabled = disabledSet.has(idx);
        const isClickable = !isDisabled && idx !== activeStep;
        const isLast = idx === steps.length - 1;

        return (
          <Fragment key={step.key}>
            {/* Step (circle + label) — single click target */}
            <Stack
              spacing={0.5}
              alignItems="center"
              onClick={() => handleClick(idx)}
              sx={{
                cursor: isDisabled
                  ? "not-allowed"
                  : isClickable
                    ? "pointer"
                    : "default",
                userSelect: "none",
                opacity: isDisabled ? 0.55 : 1,
                transition: TRANSITION,
                flexShrink: 0,
                // Hover affordance — only on clickable, enabled steps
                ...(isClickable && {
                  "&:hover .step-label": { color: "primary.main" },
                }),
              }}
            >
              <StepCircle index={idx} state={state} />
              <Typography
                className="step-label"
                variant="caption"
                fontWeight={state === "active" ? 600 : 500}
                sx={{
                  color: state === "pending" ? "text.disabled" : "text.primary",
                  fontSize: "0.72rem",
                  whiteSpace: "nowrap",
                  transition: TRANSITION,
                }}
              >
                {step.label}
              </Typography>
            </Stack>

            {/* Connector — fills with primary color when the left step
                is completed (i.e. activeStep > idx). mt aligns the line
                with the vertical center of the circle. */}
            {!isLast && (
              <Box
                sx={{
                  flex: 1,
                  height: CONNECTOR_HEIGHT,
                  bgcolor: idx < activeStep ? "primary.main" : "divider",
                  mx: 1.5,
                  mt: `${CIRCLE_SIZE / 2 - CONNECTOR_HEIGHT / 2}px`,
                  transition: TRANSITION,
                }}
              />
            )}
          </Fragment>
        );
      })}
    </Stack>
  );
}

// ==============================|| PROP TYPES ||============================== //

WizardStepper.propTypes = {
  steps: PropTypes.arrayOf(
    PropTypes.shape({
      key: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired,
    }),
  ).isRequired,
  activeStep: PropTypes.number.isRequired,
  onStepClick: PropTypes.func,
  disabledSteps: PropTypes.arrayOf(PropTypes.number),
};
