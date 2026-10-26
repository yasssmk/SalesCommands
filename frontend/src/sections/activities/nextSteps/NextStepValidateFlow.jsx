// frontend/src/sections/activities/nextSteps/NextStepValidateFlow.jsx
//
// Sprint Next steps 5.6 — the validation FLOW of a next step, in the workspace
// coque (opened by the row ✓ and by the detail's Validate). A next step is
// validated ONLY with its activity (rule 2.1): this flow never calls
// validateSignal — the server validates it when the activity is created from
// it (or linked to it, 5.7).
//
// Step 1 — "How do you resolve this next step?": Create the activity (the
// caller opens the pre-filled ActivityModal) OR Link to an existing activity
// (disabled, with a message, when GET link-candidates returns none; its steps
// 2-3 come in 5.7). Chassis: WizardStepper + DrawerContentLayout (Back / Next).

"use client";

import PropTypes from "prop-types";
import { useState } from "react";

// MUI
import FormControlLabel from "@mui/material/FormControlLabel";
import Radio from "@mui/material/Radio";
import RadioGroup from "@mui/material/RadioGroup";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Project
import { useNextStepLinkCandidates } from "api/signals/signals";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import WizardStepper from "sections/activities/signals/wizard/WizardStepper";

export const NEXT_STEP_RESOLUTION = { CREATE: "CREATE", LINK: "LINK" };

const FLOW_STEPS = [
  { key: "resolution", label: "Resolution" },
  { key: "activity", label: "Activity" },
  { key: "differences", label: "Differences" },
];

export default function NextStepValidateFlow({ nextStep, onCreate, onBack }) {
  const [choice, setChoice] = useState(null);
  const { candidates, candidatesLoading } = useNextStepLinkCandidates(nextStep.id);
  const canLink = !candidatesLoading && candidates.length > 0;

  const handleNext = () => {
    if (choice === NEXT_STEP_RESOLUTION.CREATE) onCreate(nextStep);
    // LINK: its steps 2-3 are wired in 5.7.
  };

  return (
    <Stack spacing={2} data-testid="next-step-validate-flow">
      <WizardStepper steps={FLOW_STEPS} activeStep={0} onStepClick={() => {}} />
      <DrawerContentLayout
        onSave={handleNext}
        onCancel={onBack}
        saveLabel="Next"
        cancelLabel="Back"
        saveDisabled={choice !== NEXT_STEP_RESOLUTION.CREATE}
      >
        <Typography variant="subtitle1" sx={{ fontWeight: "medium", mb: 1 }}>
          How do you resolve this next step?
        </Typography>
        <RadioGroup value={choice ?? ""} onChange={(e) => setChoice(e.target.value)}>
          <FormControlLabel
            value={NEXT_STEP_RESOLUTION.CREATE}
            control={<Radio />}
            label="Create the activity"
          />
          <FormControlLabel
            value={NEXT_STEP_RESOLUTION.LINK}
            control={<Radio />}
            label="Link to an existing activity"
            disabled={!canLink}
          />
        </RadioGroup>
        {!candidatesLoading && !canLink && (
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", pl: 4 }}>
            No open activity in this cycle
          </Typography>
        )}
      </DrawerContentLayout>
    </Stack>
  );
}

NextStepValidateFlow.propTypes = {
  /** The next step being validated (id + its proposal). */
  nextStep: PropTypes.shape({ id: PropTypes.string.isRequired }).isRequired,
  /** (nextStep) => void — Create the activity: the caller opens ActivityModal. */
  onCreate: PropTypes.func.isRequired,
  /** Back — the caller returns to the detail. */
  onBack: PropTypes.func.isRequired,
};
