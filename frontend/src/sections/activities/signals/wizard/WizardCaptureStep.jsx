// frontend/src/sections/activities/signals/wizard/WizardCaptureStep.jsx
/**
 * WizardCaptureStep — first step of the signal capture wizard.
 *
 * Responsibilities:
 *   - Render an internal segmented control (Pain | Objective | TechStack)
 *     with per-type staged-count badges
 *   - Mount the active section (PainSection / ObjectiveSection /
 *     TechStackSection) with its handlers piped through
 *   - Manage the "leave unsaved form?" confirmation when the rep
 *     switches sections with an open inline form
 *   - Footer with `Ready X/Y` chip + "Review →" button to advance
 *     to the Validation step
 *
 * State ownership
 * ---------------
 * WizardCaptureStep owns the section navigation locally:
 *   - activeSection      : which type is currently in view
 *   - sectionFormOpen    : whether the active section has an open
 *                          inline form (create OR edit)
 *   - pendingSection     : section the user wants to navigate to
 *                          while a form is open (held until
 *                          confirmation)
 *
 * The wizard parent (WizardSignalAdd) owns staged signals, the edit
 * cursor, dispatch, and the active wizard step (Capture vs Validation).
 * It passes them down via props.
 *
 * Edit-from-Validation flow
 * -------------------------
 * When the user clicks Edit on a staged signal from the Validation
 * step recap, the wizard parent sets `editing = { type, _key }` and
 * switches the active wizard step back to Capture (this component).
 * On mount/update, this step reconciles `activeSection` to
 * `editing.type` so the inline form is rendered immediately on the
 * right section.
 *
 * Edge case (acceptable for MVP)
 * ------------------------------
 * If the rep clicks the Validation step circle in the wizard stepper
 * while an inline form is open here, the form is unmounted without
 * triggering this step's confirmation dialog. The general Discard
 * close confirmation at the wizard level still protects against
 * outright dialog closure. A future iteration could lift
 * `sectionFormOpen` to the wizard parent and gate stepper navigation
 * on it.
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo, useEffect } from "react";

// material-ui
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import Stack from "@mui/material/Stack";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";

// ant-design icons
import ArrowRightOutlined from "@ant-design/icons/ArrowRightOutlined";

// project imports
import PainSection from "./sections/PainSection";
import ObjectiveSection from "./sections/ObjectiveSection";
import TechStackSection from "./sections/TechStackSection";

// ==============================|| CONSTANTS ||============================== //

/**
 * Type options for the segmented control. Order is meaningful — first
 * type is the default landing on initial mount.
 */
const TYPE_OPTIONS = [
  { value: "pain", label: "Pain" },
  { value: "objective", label: "Objective" },
  { value: "tech-stack", label: "Tech Stack" },
];

const DEFAULT_SECTION = "pain";

// ==============================|| WIZARD CAPTURE STEP ||============================== //

/**
 * WizardCaptureStep
 *
 * @param {Object}   staged              - Per-type staged arrays
 *                                         { pain, objective, 'tech-stack' }
 * @param {Object}   editing             - { type, _key } | null — edit cursor
 * @param {Function} onAdd               - (type, payload) => void
 * @param {Function} onToggleStatus      - (type, _key) => void
 * @param {Function} onRemove            - (type, _key) => void
 * @param {Function} onStartEdit         - (type, _key) => void
 * @param {Function} onUpdate            - (type, _key, payload) => void
 * @param {Function} onCancelEdit        - () => void
 * @param {Function} onReviewClick       - () => void — advance to Validation step
 * @param {Object}   choices             - From useGetSignalChoices()
 * @param {boolean}  choicesLoading
 * @param {string}   accountId
 */
export default function WizardCaptureStep({
  staged,
  editing,
  onAdd,
  onToggleStatus,
  onRemove,
  onStartEdit,
  onUpdate,
  onCancelEdit,
  onReviewClick,
  choices,
  choicesLoading,
  accountId,
}) {
  // ==============================|| STATE ||============================== //

  const [activeSection, setActiveSection] = useState(DEFAULT_SECTION);

  /** True when the active section has an inline form open with unsaved input */
  const [sectionFormOpen, setSectionFormOpen] = useState(false);

  /**
   * Section the user wants to navigate to, held while the
   * "leave unsaved form?" confirmation dialog is open.
   */
  const [pendingSection, setPendingSection] = useState(null);

  // ==============================|| AUTO-SWITCH TO EDIT TARGET ||============================== //

  /**
   * If the wizard's edit cursor lands on a signal whose type is not
   * the currently-shown section (e.g. user clicked Edit on a staged
   * Pain from the Validation step recap), align the active section
   * to the editing target so the inline form is rendered immediately.
   */
  useEffect(() => {
    if (editing?.type && editing.type !== activeSection) {
      setActiveSection(editing.type);
      setSectionFormOpen(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editing?.type, editing?._key]);

  // ==============================|| DERIVED ||============================== //

  /** Per-type counts shown as badges in the segmented control */
  const counts = useMemo(
    () => ({
      pain: staged.pain.length,
      objective: staged.objective.length,
      "tech-stack": staged["tech-stack"].length,
    }),
    [staged],
  );

  const totalStaged = useMemo(
    () => Object.values(counts).reduce((a, b) => a + b, 0),
    [counts],
  );

  const validatedCount = useMemo(
    () =>
      Object.values(staged)
        .flat()
        .filter((s) => s._status === "VALIDATED").length,
    [staged],
  );

  // ==============================|| NAVIGATION HANDLERS ||============================== //

  const handleSectionChange = useCallback(
    (_e, newValue) => {
      if (newValue === null) return;
      if (sectionFormOpen) {
        // A form is open in the current section — ask before navigating away
        setPendingSection(newValue);
        return;
      }
      setActiveSection(newValue);
    },
    [sectionFormOpen],
  );

  /** User confirms leaving the section with an unsaved form */
  const handleSectionChangeProceed = useCallback(() => {
    if (pendingSection) {
      setSectionFormOpen(false);
      setActiveSection(pendingSection);
      setPendingSection(null);
      onCancelEdit?.();
    }
  }, [pendingSection, onCancelEdit]);

  /** User cancels — stays on the current section */
  const handleSectionChangeDismiss = useCallback(() => {
    setPendingSection(null);
  }, []);

  // ==============================|| SECTION RENDERING ||============================== //

  /**
   * Editing key resolver — only expose the edit cursor to the section
   * that owns the signal being edited. Other sections see null.
   */
  const editingKeyFor = (type) =>
    editing?.type === type ? editing._key : null;

  const sharedProps = {
    choices,
    choicesLoading,
    accountId,
    onFormOpenChange: setSectionFormOpen,
    onCancelEdit,
  };

  const renderSection = () => {
    switch (activeSection) {
      case "pain":
        return (
          <PainSection
            stagedSignals={staged.pain}
            onAdd={(payload) => onAdd("pain", payload)}
            onToggleStatus={(_key) => onToggleStatus("pain", _key)}
            onRemove={(_key) => onRemove("pain", _key)}
            onEdit={(_key) => onStartEdit("pain", _key)}
            onUpdate={(_key, payload) => onUpdate("pain", _key, payload)}
            editingKey={editingKeyFor("pain")}
            {...sharedProps}
          />
        );
      case "objective":
        return (
          <ObjectiveSection
            stagedSignals={staged.objective}
            onAdd={(payload) => onAdd("objective", payload)}
            onToggleStatus={(_key) => onToggleStatus("objective", _key)}
            onRemove={(_key) => onRemove("objective", _key)}
            onEdit={(_key) => onStartEdit("objective", _key)}
            onUpdate={(_key, payload) => onUpdate("objective", _key, payload)}
            editingKey={editingKeyFor("objective")}
            {...sharedProps}
          />
        );
      case "tech-stack":
        return (
          <TechStackSection
            stagedSignals={staged["tech-stack"]}
            onAdd={(payload) => onAdd("tech-stack", payload)}
            onToggleStatus={(_key) => onToggleStatus("tech-stack", _key)}
            onRemove={(_key) => onRemove("tech-stack", _key)}
            onEdit={(_key) => onStartEdit("tech-stack", _key)}
            onUpdate={(_key, payload) => onUpdate("tech-stack", _key, payload)}
            editingKey={editingKeyFor("tech-stack")}
            {...sharedProps}
          />
        );
      default:
        return null;
    }
  };

  // ==============================|| RENDER ||============================== //

  return (
    <Stack
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* ---- Segmented control ---- */}
      <Box sx={{ px: 3, pt: 2.5, pb: 1.5, flexShrink: 0 }}>
        <ToggleButtonGroup
          value={activeSection}
          exclusive
          onChange={handleSectionChange}
          size="small"
          fullWidth
          aria-label="Signal section"
        >
          {TYPE_OPTIONS.map((opt) => (
            <ToggleButton
              key={opt.value}
              value={opt.value}
              sx={{ textTransform: "none", px: 1.5, fontSize: "0.78rem" }}
            >
              {opt.label}
              {counts[opt.value] > 0 && (
                <Chip
                  label={counts[opt.value]}
                  size="small"
                  sx={{
                    ml: 0.75,
                    height: 18,
                    fontSize: "0.62rem",
                    pointerEvents: "none",
                  }}
                />
              )}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </Box>

      {/* ---- Section content — scrollable ---- */}
      <Box sx={{ flex: 1, overflowY: "auto", px: 3, py: 2 }}>
        {renderSection()}
      </Box>

      <Divider sx={{ flexShrink: 0 }} />

      {/* ---- Footer ---- */}
      <Box sx={{ px: 3, py: 2, flexShrink: 0 }}>
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
        >
          {/* Staged count chip — shows ready/total to make exclusions visible */}
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="caption" color="text.secondary">
              Ready
            </Typography>
            <Chip
              label={
                totalStaged === 0
                  ? "0"
                  : validatedCount === totalStaged
                    ? `${totalStaged}`
                    : `${validatedCount} / ${totalStaged}`
              }
              size="small"
              color={
                validatedCount === 0
                  ? "default"
                  : validatedCount < totalStaged
                    ? "warning"
                    : "primary"
              }
              sx={{ height: 20, fontSize: "0.68rem" }}
            />
          </Stack>

          {/* Review → button — enabled as long as something is staged,
              even if all are excluded (user can re-include in Validation) */}
          <Button
            variant="contained"
            size="small"
            onClick={onReviewClick}
            disabled={totalStaged === 0}
            endIcon={<ArrowRightOutlined style={{ fontSize: 13 }} />}
          >
            Review
          </Button>
        </Stack>
      </Box>

      {/* ---- Section change confirmation dialog ---- */}
      <Dialog
        open={Boolean(pendingSection)}
        onClose={handleSectionChangeDismiss}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Leave unsaved form?</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary">
            You have an unsaved signal form open. Switching sections will
            discard what you&apos;ve typed.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button
            onClick={handleSectionChangeDismiss}
            color="inherit"
            size="small"
          >
            Stay here
          </Button>
          <Button
            onClick={handleSectionChangeProceed}
            color="warning"
            variant="contained"
            size="small"
          >
            Leave anyway
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}

// ==============================|| PROP TYPES ||============================== //

WizardCaptureStep.propTypes = {
  staged: PropTypes.shape({
    pain: PropTypes.array.isRequired,
    objective: PropTypes.array.isRequired,
    "tech-stack": PropTypes.array.isRequired,
  }).isRequired,
  editing: PropTypes.shape({
    type: PropTypes.string,
    _key: PropTypes.string,
  }),
  onAdd: PropTypes.func.isRequired,
  onToggleStatus: PropTypes.func.isRequired,
  onRemove: PropTypes.func.isRequired,
  onStartEdit: PropTypes.func.isRequired,
  onUpdate: PropTypes.func.isRequired,
  onCancelEdit: PropTypes.func.isRequired,
  onReviewClick: PropTypes.func.isRequired,
  choices: PropTypes.object,
  choicesLoading: PropTypes.bool,
  accountId: PropTypes.string.isRequired,
};
