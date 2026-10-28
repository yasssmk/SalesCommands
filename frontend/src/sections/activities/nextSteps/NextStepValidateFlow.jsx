// frontend/src/sections/activities/nextSteps/NextStepValidateFlow.jsx
//
// Sprint Next steps 5.6 / 5.7 — the validation FLOW of a next step, in the
// workspace coque (opened by the row ✓ and by the detail's Validate). A next
// step is validated ONLY with its activity (rule 2.1): this flow never calls
// validateSignal — the server validates it when the activity is created from
// it, or when it is linked to one (attach-activity, same transaction).
//
// Step 1 — "How do you resolve this next step?": Create the activity (the
//   caller opens the pre-filled ActivityModal) OR Link to an existing activity
//   (disabled, with a message, when GET link-candidates returns none).
// Step 2 (Link) — the candidates IN THE SERVER ORDER, the first one marked
//   "Proposed" and pre-selected; each one = the existing ActivityMiniCard + a
//   readable "Why" (shared people / step / type / date gap). Single choice.
//   Next → step 3, or Confirm at once when the candidate has no difference.
// Step 3 (Link) — the candidate's differences, one section per difference
//   (ABSENT when none): type / date / step = Keep (default) or Use proposed;
//   objective / description = the proposed text, editable, + "Append to the
//   current …" (unchecked); contacts = "Add <name>" (unchecked). Only the
//   "Use proposed" choices and the checked boxes go into `updates`.
// Confirm → POST attach-activity {activity_id, updates}; on success the
//   caller reads the next step back; a server refusal → the standard error,
//   the flow stays on its step with every choice kept. Back never loses a
//   choice (the state lives here, per candidate).
// Chassis: WizardStepper + DrawerContentLayout (Back / Next / Confirm).

"use client";

import PropTypes from "prop-types";
import { useState } from "react";

// MUI
import Box from "@mui/material/Box";
import Checkbox from "@mui/material/Checkbox";
import FormControlLabel from "@mui/material/FormControlLabel";
import Radio from "@mui/material/Radio";
import RadioGroup from "@mui/material/RadioGroup";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

// Project
import { attachNextStepToActivity, useNextStepLinkCandidates } from "api/signals/signals";
import { ACTIVITY_TYPE_LABELS } from "api/accounts/activities";
import { displayErrorSnackbar } from "utils/displayError";
import ActivityMiniCard, {
  ACTIVITY_MINI_CARD_LAYOUTS,
} from "components/cards/activities/ActivityMiniCard";
import StatusPill from "components/chips/StatusPill";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import { formatShortDate } from "components/signals/SignalLine";
import WizardStepper from "sections/activities/signals/wizard/WizardStepper";
import { SCOPE_PILL_COLORS } from "utils/objectiveScope";

export const NEXT_STEP_RESOLUTION = { CREATE: "CREATE", LINK: "LINK" };

const FLOW_STEPS = [
  { key: "resolution", label: "Resolution" },
  { key: "activity", label: "Activity" },
  { key: "differences", label: "Differences" },
];
const STEP = { RESOLUTION: 0, CANDIDATES: 1, DIFFERENCES: 2 };

const KEEP = "KEEP";
const PROPOSED = "PROPOSED";

// The single-choice differences: how each value reads, and what "Use
// proposed" sends (NEXT_STEP_LINK_UPDATE_FIELDS).
const CHOICE_FIELDS = [
  {
    key: "activity_type",
    label: "Type",
    format: (v) => (v ? ACTIVITY_TYPE_LABELS[v] || v : "No type"),
    update: (proposed) => ({ activity_type: proposed }),
  },
  {
    key: "date",
    label: "Date",
    format: (v) => (v?.value ? formatShortDate(v.value) : "No date"),
    // The proposed date carries its own field (scheduled_date / due_date).
    update: (proposed) => ({ [proposed.field]: proposed.value }),
  },
  {
    key: "decision_step",
    label: "Step",
    format: (v) => v?.name || "No step",
    update: (proposed) => ({ decision_step_id: proposed.id }),
  },
];

const TEXT_FIELDS = [
  { key: "call_to_action", label: "Objective", appendLabel: "Append to the current objective" },
  { key: "description", label: "Description", appendLabel: "Append to the current description" },
];

const TEXT_SEPARATOR = "\n\n";

// "Why" this candidate, read from the ranking criteria (PO decision A,
// 5.10b): ONLY the criteria that match — « N people in common » (N > 0),
// « Same step », « Same type » — then always the date gap (« 29 days apart »,
// « Same day », nothing without a date). No negative criterion; "" when
// nothing applies.
export function linkCandidateWhy(c) {
  const n = c.shared_people_count ?? 0;
  const d = c.date_distance_days;
  const dateGap =
    d === null || d === undefined
      ? null
      : d === 0
        ? "Same day"
        : `${d} ${d === 1 ? "day" : "days"} apart`;
  return [
    n > 0 ? `${n} ${n === 1 ? "person" : "people"} in common` : null,
    c.same_step ? "Same step" : null,
    c.same_type ? "Same type" : null,
    dateGap,
  ]
    .filter(Boolean)
    .join(" · ");
}

const hasDifferences = (c) => Object.keys(c?.differences ?? {}).length > 0;

// Default decisions for a candidate: keep everything, texts = the proposals,
// nothing appended, no contact added.
function defaultDecisions(candidate) {
  const diff = candidate.differences ?? {};
  return {
    choices: Object.fromEntries(CHOICE_FIELDS.map((f) => [f.key, KEEP])),
    texts: Object.fromEntries(
      TEXT_FIELDS.filter((f) => diff[f.key]).map((f) => [
        f.key,
        { text: diff[f.key].proposed, append: false },
      ]),
    ),
    contacts: [],
  };
}

// The decisions → `updates`: only "Use proposed" and the checked boxes.
export function buildLinkUpdates(candidate, decisions) {
  const diff = candidate.differences ?? {};
  const updates = {};
  CHOICE_FIELDS.forEach((f) => {
    if (diff[f.key] && decisions.choices[f.key] === PROPOSED) {
      Object.assign(updates, f.update(diff[f.key].proposed));
    }
  });
  TEXT_FIELDS.forEach((f) => {
    const t = decisions.texts[f.key];
    if (diff[f.key] && t?.append) {
      const current = diff[f.key].current;
      updates[f.key] = current ? `${current}${TEXT_SEPARATOR}${t.text}` : t.text;
    }
  });
  const toAdd = (diff.contacts?.to_add ?? []).filter((c) => decisions.contacts.includes(c.id));
  if (toAdd.length) updates.add_contact_ids = toAdd.map((c) => c.id);
  return updates;
}

// ==============================|| NEXT STEP VALIDATE FLOW ||============================== //

export default function NextStepValidateFlow({ nextStep, onCreate, onBack, onLinked }) {
  const [step, setStep] = useState(STEP.RESOLUTION);
  const [choice, setChoice] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [decisionsById, setDecisionsById] = useState({});
  const [submitting, setSubmitting] = useState(false);

  const { candidates, proposedActivityId, candidatesLoading } = useNextStepLinkCandidates(
    nextStep.id,
  );
  const canLink = !candidatesLoading && candidates.length > 0;

  // The first candidate (the server's proposal) is pre-selected.
  const currentId = selectedId ?? proposedActivityId ?? candidates[0]?.id ?? null;
  const selected = candidates.find((c) => c.id === currentId) ?? null;
  const decisions = selected ? decisionsById[selected.id] ?? defaultDecisions(selected) : null;

  const setDecisions = (patch) =>
    setDecisionsById((all) => ({ ...all, [selected.id]: { ...decisions, ...patch } }));

  const confirm = async () => {
    setSubmitting(true);
    const result = await attachNextStepToActivity(
      nextStep.id,
      selected.id,
      buildLinkUpdates(selected, decisions),
    );
    setSubmitting(false);
    if (result.success) {
      onLinked(nextStep);
    } else {
      // A server refusal (campaign lock, no longer a candidate…): the standard
      // error, and the flow stays here, every choice kept.
      displayErrorSnackbar(result);
    }
  };

  // ---- Step-dependent action bar ----
  let bar;
  if (step === STEP.RESOLUTION) {
    bar = {
      onSave: () => {
        if (choice === NEXT_STEP_RESOLUTION.CREATE) onCreate(nextStep);
        else setStep(STEP.CANDIDATES);
      },
      onCancel: onBack,
      saveLabel: "Next",
      saveDisabled: !(
        choice === NEXT_STEP_RESOLUTION.CREATE || (choice === NEXT_STEP_RESOLUTION.LINK && canLink)
      ),
    };
  } else if (step === STEP.CANDIDATES) {
    const direct = !hasDifferences(selected);
    bar = {
      onSave: direct ? confirm : () => setStep(STEP.DIFFERENCES),
      onCancel: () => setStep(STEP.RESOLUTION),
      saveLabel: direct ? "Confirm" : "Next",
      saveDisabled: !selected || submitting,
    };
  } else {
    bar = {
      onSave: confirm,
      onCancel: () => setStep(STEP.CANDIDATES),
      saveLabel: "Confirm",
      saveDisabled: submitting,
    };
  }

  return (
    <Stack spacing={2} data-testid="next-step-validate-flow">
      <WizardStepper steps={FLOW_STEPS} activeStep={step} onStepClick={() => {}} />
      <DrawerContentLayout
        onSave={bar.onSave}
        onCancel={bar.onCancel}
        saveLabel={bar.saveLabel}
        cancelLabel="Back"
        saveDisabled={bar.saveDisabled}
      >
        {step === STEP.RESOLUTION && (
          <ResolutionStep choice={choice} onChoice={setChoice} canLink={canLink} loading={candidatesLoading} />
        )}
        {step === STEP.CANDIDATES && (
          <CandidatesStep
            candidates={candidates}
            selectedId={currentId}
            onSelect={setSelectedId}
          />
        )}
        {step === STEP.DIFFERENCES && selected && (
          <DifferencesStep candidate={selected} decisions={decisions} onChange={setDecisions} />
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
  /** Back from step 1 — the caller returns to the detail. */
  onBack: PropTypes.func.isRequired,
  /** (nextStep) => void — linked: the caller reads it back and shows it. */
  onLinked: PropTypes.func.isRequired,
};

// ==============================|| STEP 1 — RESOLUTION ||============================== //

function ResolutionStep({ choice, onChoice, canLink, loading }) {
  return (
    <>
      <Typography variant="subtitle1" sx={{ fontWeight: "medium", mb: 1 }}>
        How do you resolve this next step?
      </Typography>
      <RadioGroup value={choice ?? ""} onChange={(e) => onChoice(e.target.value)}>
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
      {!loading && !canLink && (
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", pl: 4 }}>
          No open activity in this cycle
        </Typography>
      )}
    </>
  );
}
ResolutionStep.propTypes = {
  choice: PropTypes.string,
  onChoice: PropTypes.func.isRequired,
  canLink: PropTypes.bool,
  loading: PropTypes.bool,
};

// ==============================|| STEP 2 — CANDIDATES ||============================== //

function CandidatesStep({ candidates, selectedId, onSelect }) {
  return (
    <Stack spacing={1.5} data-testid="link-candidates">
      <Typography variant="subtitle1" sx={{ fontWeight: "medium" }}>
        Which activity does this next step become?
      </Typography>
      {candidates.map((c, index) => (
        <Stack
          key={c.id}
          direction="row"
          spacing={1}
          alignItems="flex-start"
          data-testid={`link-candidate-${c.id}`}
        >
          <Radio
            checked={c.id === selectedId}
            onChange={() => onSelect(c.id)}
            inputProps={{ "aria-label": `Select ${c.title}` }}
            sx={{ mt: 0.5 }}
          />
          <Stack spacing={0.5} sx={{ flex: 1, minWidth: 0 }}>
            {index === 0 && (
              <StatusPill
                label="Proposed"
                colorText={SCOPE_PILL_COLORS.active.colorText}
                colorBg={SCOPE_PILL_COLORS.active.colorBg}
                sx={{ alignSelf: "flex-start" }}
              />
            )}
            {/* The existing card; a click selects the candidate. */}
            <ActivityMiniCard
              activity={{ ...c, decision_step_name: c.decision_step?.name }}
              onNavigate={() => onSelect(c.id)}
              layout={ACTIVITY_MINI_CARD_LAYOUTS.DRAWER}
            />
            {linkCandidateWhy(c) && (
              <Typography variant="caption" color="text.secondary">
                {`Why: ${linkCandidateWhy(c)}`}
              </Typography>
            )}
          </Stack>
        </Stack>
      ))}
    </Stack>
  );
}
CandidatesStep.propTypes = {
  candidates: PropTypes.arrayOf(PropTypes.object).isRequired,
  selectedId: PropTypes.string,
  onSelect: PropTypes.func.isRequired,
};

// ==============================|| STEP 3 — DIFFERENCES ||============================== //

function DiffLabel({ children }) {
  return (
    <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.5 }}>
      {children}
    </Typography>
  );
}
DiffLabel.propTypes = { children: PropTypes.node };

function DifferencesStep({ candidate, decisions, onChange }) {
  const diff = candidate.differences ?? {};
  const toAdd = diff.contacts?.to_add ?? [];

  return (
    <Stack spacing={2} data-testid="link-differences">
      <Typography variant="subtitle1" sx={{ fontWeight: "medium" }}>
        What should change on “{candidate.title}”?
      </Typography>

      {/* Single choices — Keep (default) or Use proposed. */}
      {CHOICE_FIELDS.filter((f) => diff[f.key]).map((f) => (
        <Box key={f.key} data-testid={`link-diff-${f.key}`}>
          <DiffLabel>{f.label}</DiffLabel>
          <RadioGroup
            value={decisions.choices[f.key]}
            onChange={(e) =>
              onChange({ choices: { ...decisions.choices, [f.key]: e.target.value } })
            }
          >
            <FormControlLabel
              value={KEEP}
              control={<Radio size="small" />}
              label={`Keep: ${f.format(diff[f.key].current)}`}
            />
            <FormControlLabel
              value={PROPOSED}
              control={<Radio size="small" />}
              label={`Use proposed: ${f.format(diff[f.key].proposed)}`}
            />
          </RadioGroup>
        </Box>
      ))}

      {/* Texts — the proposal, editable, appended only when checked. */}
      {TEXT_FIELDS.filter((f) => diff[f.key]).map((f) => {
        const t = decisions.texts[f.key];
        const setText = (patch) =>
          onChange({ texts: { ...decisions.texts, [f.key]: { ...t, ...patch } } });
        return (
          <Box key={f.key} data-testid={`link-diff-${f.key}`}>
            <DiffLabel>{f.label}</DiffLabel>
            {diff[f.key].current && (
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1, whiteSpace: "pre-line" }}>
                {`Current: ${diff[f.key].current}`}
              </Typography>
            )}
            <TextField
              fullWidth
              multiline
              size="small"
              value={t.text}
              onChange={(e) => setText({ text: e.target.value })}
              inputProps={{ "data-testid": `link-text-${f.key}` }}
            />
            <FormControlLabel
              control={
                <Checkbox
                  size="small"
                  checked={t.append}
                  onChange={(e) => setText({ append: e.target.checked })}
                />
              }
              label={f.appendLabel}
            />
          </Box>
        );
      })}

      {/* Contacts — added only when checked. */}
      {toAdd.length > 0 && (
        <Box data-testid="link-diff-contacts">
          <DiffLabel>Contacts</DiffLabel>
          <Stack>
            {toAdd.map((c) => {
              const name = `${c.first_name ?? ""} ${c.last_name ?? ""}`.trim();
              return (
                <FormControlLabel
                  key={c.id}
                  control={
                    <Checkbox
                      size="small"
                      checked={decisions.contacts.includes(c.id)}
                      onChange={(e) =>
                        onChange({
                          contacts: e.target.checked
                            ? [...decisions.contacts, c.id]
                            : decisions.contacts.filter((id) => id !== c.id),
                        })
                      }
                    />
                  }
                  label={`Add ${name}`}
                />
              );
            })}
          </Stack>
        </Box>
      )}
    </Stack>
  );
}
DifferencesStep.propTypes = {
  candidate: PropTypes.object.isRequired,
  decisions: PropTypes.object.isRequired,
  onChange: PropTypes.func.isRequired,
};
