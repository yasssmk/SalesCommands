// frontend/src/sections/activities/workspace/PeopleValidateFlow.jsx
//
// Sprint « Cycle de vie des contacts », étape 5 (4) — validating a People
// signal on the Activity surface = « true? » + « which stakeholder of the
// DC? », on the generic ResolutionFlow (the next step's gestures —
// homogeneity, PO). Opened by the Signals band (row ✓, detail's Validate).
//
// Step 1 — "Who is this person in the decision cycle?":
//   Link to an existing stakeholder or contact (disabled when there is no
//   candidate) OR Create a new stakeholder.
// Step 2 (Link) — ONE list: the stakeholders of the DC, then the account
//   contacts not yet stakeholders (the shortcut: the server creates the
//   stakeholder linked to the contact). The EXACT match (same contact, same
//   normalised name — server-side) carries « Proposed » and is pre-selected,
//   never applied without Confirm.
// Step 2 (Create) — a « not linked » stakeholder: its name (pre-filled from
//   the signal; a first name is enough) and / or a department.
// Confirm → POST /people/{id}/resolve/ (validation + affiliation in one
//   transaction). No contact is ever created here; no role step.
// A server refusal → the standard error, the flow stays on its step.

"use client";

import PropTypes from "prop-types";
import { useMemo, useState } from "react";

// MUI
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

// Project
import { resolvePeopleSignal, usePeopleResolutionCandidates } from "api/signals/signals";
import { useGetContactChoices } from "api/businessData/contacts";
import { displayErrorSnackbar } from "utils/displayError";
import ResolutionFlow, {
  CandidateList,
  ResolutionChoiceStep,
} from "components/flows/ResolutionFlow";

export const PEOPLE_RESOLUTION = { LINK: "LINK", CREATE: "CREATE" };

const FLOW_STEPS = [
  { key: "resolution", label: "Resolution" },
  { key: "stakeholder", label: "Stakeholder" },
];
const STEP = { RESOLUTION: 0, DETAILS: 1 };

const personName = (p) => `${p?.first_name ?? ""} ${p?.last_name ?? ""}`.trim();

// The candidates as ONE list: the DC stakeholders, then the account contacts.
function toCandidates(stakeholders, contacts) {
  return [
    ...stakeholders.map((s) => ({
      id: s.id,
      kind: "stakeholder",
      label: (s.contact ? personName(s.contact) : s.full_name) || s.department?.name || "",
      caption: [
        "Stakeholder",
        s.current_role_display,
        s.contact ? null : "Not linked",
      ].filter(Boolean).join(" · "),
      proposed: Boolean(s.proposed),
    })),
    ...contacts.map((c) => ({
      id: c.id,
      kind: "contact",
      label: personName(c),
      caption: ["Account contact", c.job_title].filter(Boolean).join(" · "),
      proposed: Boolean(c.proposed),
    })),
  ];
}

export default function PeopleValidateFlow({ signal, onBack, onResolved }) {
  const [step, setStep] = useState(STEP.RESOLUTION);
  const [choice, setChoice] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [name, setName] = useState(signal.full_name || "");
  const [departmentId, setDepartmentId] = useState(
    String(signal.target_department?.id ?? signal.target_department ?? ""),
  );
  const [submitting, setSubmitting] = useState(false);

  const { stakeholders, contacts, candidatesLoading } = usePeopleResolutionCandidates(signal.id);
  const { standardDepartments } = useGetContactChoices();

  const candidates = useMemo(() => toCandidates(stakeholders, contacts), [stakeholders, contacts]);
  const canLink = !candidatesLoading && candidates.length > 0;

  // The exact match (server-side) is pre-selected; otherwise nothing is.
  const currentId = selectedId ?? candidates.find((c) => c.proposed)?.id ?? null;
  const selected = candidates.find((c) => c.id === currentId) ?? null;
  const createReady = Boolean(name.trim() || departmentId);

  const resolve = async (resolution) => {
    setSubmitting(true);
    const result = await resolvePeopleSignal(signal.id, resolution);
    setSubmitting(false);
    if (result.success) {
      onResolved(result.data ?? {});
    } else {
      displayErrorSnackbar(result);
    }
  };

  const confirm = () => {
    if (choice === PEOPLE_RESOLUTION.CREATE) {
      const create = {};
      if (name.trim()) create.full_name = name.trim();
      if (departmentId) create.department_id = departmentId;
      return resolve({ create });
    }
    return resolve(
      selected.kind === "stakeholder" ? { stakeholder_id: selected.id } : { contact_id: selected.id },
    );
  };

  const bar =
    step === STEP.RESOLUTION
      ? {
          onSave: () => setStep(STEP.DETAILS),
          onCancel: onBack,
          saveLabel: "Next",
          saveDisabled: !(
            choice === PEOPLE_RESOLUTION.CREATE || (choice === PEOPLE_RESOLUTION.LINK && canLink)
          ),
        }
      : {
          onSave: confirm,
          onCancel: () => setStep(STEP.RESOLUTION),
          saveLabel: "Confirm",
          saveDisabled:
            submitting || (choice === PEOPLE_RESOLUTION.CREATE ? !createReady : !selected),
        };

  return (
    <ResolutionFlow steps={FLOW_STEPS} activeStep={step} bar={bar} testId="people-validate-flow">
      {step === STEP.RESOLUTION && (
        <ResolutionChoiceStep
          title="Who is this person in the decision cycle?"
          options={[
            {
              value: PEOPLE_RESOLUTION.LINK,
              label: "Link to an existing stakeholder or contact",
              disabled: !canLink,
            },
            { value: PEOPLE_RESOLUTION.CREATE, label: "Create a new stakeholder" },
          ]}
          choice={choice}
          onChoice={setChoice}
          note={!candidatesLoading && !canLink ? "No stakeholder or contact yet" : null}
        />
      )}

      {step === STEP.DETAILS && choice === PEOPLE_RESOLUTION.LINK && (
        <CandidateList
          title="Who is this person?"
          candidates={candidates}
          selectedId={currentId}
          onSelect={setSelectedId}
          isProposed={(c) => c.proposed}
          getAriaLabel={(c) => `Select ${c.label}`}
          testId="people-candidates"
          candidateTestIdPrefix="people-candidate-"
          renderCandidate={(c) => (
            <Stack spacing={0.25}>
              <Typography variant="body2" sx={{ fontWeight: "medium" }}>
                {c.label}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {c.caption}
              </Typography>
            </Stack>
          )}
        />
      )}

      {step === STEP.DETAILS && choice === PEOPLE_RESOLUTION.CREATE && (
        <Stack spacing={2} data-testid="people-create-stakeholder">
          <Typography variant="subtitle1" sx={{ fontWeight: "medium" }}>
            New stakeholder (not linked to a contact)
          </Typography>
          <TextField
            id="people-create-name"
            label="Name"
            size="small"
            fullWidth
            value={name}
            onChange={(e) => setName(e.target.value)}
            helperText="A first name is enough."
          />
          <TextField
            id="people-create-department"
            select
            label="Department"
            size="small"
            fullWidth
            value={departmentId}
            onChange={(e) => setDepartmentId(e.target.value)}
          >
            <MenuItem value="">
              <em>None</em>
            </MenuItem>
            {(standardDepartments ?? []).map((d) => (
              <MenuItem key={String(d.value ?? d.id)} value={String(d.value ?? d.id)}>
                {d.label ?? d.name}
              </MenuItem>
            ))}
          </TextField>
        </Stack>
      )}
    </ResolutionFlow>
  );
}

PeopleValidateFlow.propTypes = {
  /** The People signal being validated (list / detail payload). */
  signal: PropTypes.shape({
    id: PropTypes.string.isRequired,
    full_name: PropTypes.string,
    target_department: PropTypes.oneOfType([PropTypes.object, PropTypes.string, PropTypes.number]),
  }).isRequired,
  /** Back from step 1 — the caller returns to the detail. */
  onBack: PropTypes.func.isRequired,
  /** (updatedSignal) => void — resolved: the caller refreshes and shows it. */
  onResolved: PropTypes.func.isRequired,
};
