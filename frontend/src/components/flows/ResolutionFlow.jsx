// frontend/src/components/flows/ResolutionFlow.jsx
//
// Sprint « Cycle de vie des contacts », étape 5 (3) — the generic RESOLUTION
// flow, EXTRACTED from NextStepValidateFlow (Sprint Next steps 5.6 / 5.7) so
// the next step and the People signal resolve with the SAME gestures
// (homogeneity, PO):
//   - ResolutionFlow      — the chassis: WizardStepper + DrawerContentLayout,
//                           the step-dependent action bar given by the caller
//                           (onSave / onCancel / saveLabel / saveDisabled),
//                           Cancel labelled "Back";
//   - ResolutionChoiceStep — the "How do you resolve …?" step: exclusive
//                           radio options (Create / Link …), an option can be
//                           disabled, an optional note below them;
//   - CandidateList       — a single-choice list of candidates (Radio + the
//                           caller's card), the "Proposed" pill on the
//                           candidates the caller's predicate marks.
// The caller owns the state (step, choice, selection) and the confirmation —
// nothing here knows what a next step or a person is.
// Step titles (lot 3 / 13d, TD-239 — PO: the numbered-section design in every
// drawer): a SectionHeader, `index` = the step's number in the stepper.

"use client";

import PropTypes from "prop-types";

// MUI
import FormControlLabel from "@mui/material/FormControlLabel";
import Radio from "@mui/material/Radio";
import RadioGroup from "@mui/material/RadioGroup";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Project
import StatusPill from "components/chips/StatusPill";
import SectionHeader from "components/display/SectionHeader";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import WizardStepper from "sections/activities/signals/wizard/WizardStepper";
import { SCOPE_PILL_COLORS } from "utils/objectiveScope";

// ==============================|| CHASSIS ||============================== //

export default function ResolutionFlow({ steps, activeStep, bar, testId, children }) {
  return (
    <Stack spacing={2} data-testid={testId}>
      <WizardStepper steps={steps} activeStep={activeStep} onStepClick={() => {}} />
      <DrawerContentLayout
        onSave={bar.onSave}
        onCancel={bar.onCancel}
        saveLabel={bar.saveLabel}
        cancelLabel="Back"
        saveDisabled={bar.saveDisabled}
        dirty={Boolean(bar.dirty)}
      >
        {children}
      </DrawerContentLayout>
    </Stack>
  );
}

ResolutionFlow.propTypes = {
  /** The wizard steps: [{ key, label }]. */
  steps: PropTypes.arrayOf(
    PropTypes.shape({ key: PropTypes.string.isRequired, label: PropTypes.node.isRequired }),
  ).isRequired,
  /** Index of the current step. */
  activeStep: PropTypes.number.isRequired,
  /** The action bar of the current step. */
  bar: PropTypes.shape({
    onSave: PropTypes.func.isRequired,
    onCancel: PropTypes.func.isRequired,
    saveLabel: PropTypes.node.isRequired,
    saveDisabled: PropTypes.bool,
    /** Optional — the caller's state holds UNSAVED choices: the coque asks
        before replacing / closing the drawer (« Source / Notes » 2.2). */
    dirty: PropTypes.bool,
  }).isRequired,
  /** data-testid of the flow root. */
  testId: PropTypes.string,
  /** The current step's content. */
  children: PropTypes.node,
};

// ==============================|| STEP — RESOLUTION CHOICE ||============================== //

export function ResolutionChoiceStep({ index, title, options, choice, onChoice, note }) {
  return (
    <>
      <SectionHeader index={index} title={title} sx={{ mb: 1 }} />
      <RadioGroup value={choice ?? ""} onChange={(e) => onChoice(e.target.value)}>
        {options.map((o) => (
          <FormControlLabel
            key={o.value}
            value={o.value}
            control={<Radio />}
            label={o.label}
            disabled={Boolean(o.disabled)}
          />
        ))}
      </RadioGroup>
      {note && (
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", pl: 4 }}>
          {note}
        </Typography>
      )}
    </>
  );
}

ResolutionChoiceStep.propTypes = {
  /** The step's number in the stepper (the SectionHeader badge). */
  index: PropTypes.number,
  title: PropTypes.node.isRequired,
  /** [{ value, label, disabled? }] in display order. */
  options: PropTypes.arrayOf(
    PropTypes.shape({
      value: PropTypes.string.isRequired,
      label: PropTypes.node.isRequired,
      disabled: PropTypes.bool,
    }),
  ).isRequired,
  choice: PropTypes.string,
  onChoice: PropTypes.func.isRequired,
  /** Optional caption below the options (e.g. why an option is disabled). */
  note: PropTypes.node,
};

// ==============================|| STEP — CANDIDATES ||============================== //

export function CandidateList({
  index,
  title,
  candidates,
  selectedId,
  onSelect,
  isProposed,
  renderCandidate,
  getAriaLabel,
  testId,
  candidateTestIdPrefix,
  emptyText,
}) {
  return (
    <Stack spacing={1.5} data-testid={testId}>
      <SectionHeader index={index} title={title} />
      {candidates.length === 0 && emptyText && (
        <Typography variant="body2" color="text.secondary">
          {emptyText}
        </Typography>
      )}
      {candidates.map((c, index) => (
        <Stack
          key={c.id}
          direction="row"
          spacing={1}
          alignItems="flex-start"
          data-testid={`${candidateTestIdPrefix}${c.id}`}
        >
          <Radio
            checked={c.id === selectedId}
            onChange={() => onSelect(c.id)}
            inputProps={{ "aria-label": getAriaLabel(c) }}
            sx={{ mt: 0.5 }}
          />
          <Stack spacing={0.5} sx={{ flex: 1, minWidth: 0 }}>
            {isProposed(c, index) && (
              <StatusPill
                label="Proposed"
                colorText={SCOPE_PILL_COLORS.active.colorText}
                colorBg={SCOPE_PILL_COLORS.active.colorBg}
                sx={{ alignSelf: "flex-start" }}
              />
            )}
            {renderCandidate(c, () => onSelect(c.id))}
          </Stack>
        </Stack>
      ))}
    </Stack>
  );
}

CandidateList.propTypes = {
  /** The step's number in the stepper (the SectionHeader badge). */
  index: PropTypes.number,
  title: PropTypes.node.isRequired,
  /** [{ id, … }] in display order. */
  candidates: PropTypes.arrayOf(PropTypes.object).isRequired,
  selectedId: PropTypes.string,
  onSelect: PropTypes.func.isRequired,
  /** (candidate, index) => bool — shows the "Proposed" pill. */
  isProposed: PropTypes.func.isRequired,
  /** (candidate, select) => node — the candidate's card. */
  renderCandidate: PropTypes.func.isRequired,
  /** (candidate) => string — the radio's aria-label. */
  getAriaLabel: PropTypes.func.isRequired,
  testId: PropTypes.string,
  /** Prefix of each candidate row's data-testid (+ id). */
  candidateTestIdPrefix: PropTypes.string.isRequired,
  /** Shown when there is no candidate. */
  emptyText: PropTypes.node,
};
