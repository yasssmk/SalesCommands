import PropTypes from 'prop-types';

// material-ui
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// third-party
import { useFormik } from 'formik';
import * as Yup from 'yup';

// project imports
import ClickablePill from 'components/chips/ClickablePill';
import InlineEditableValue from 'components/drawer/InlineEditableValue';
import ConfirmCancelActions from 'components/drawer/ConfirmCancelActions';
import { PIPELINE_STEPS_ORDER, PIPELINE_STEP_LABELS } from 'api/accounts/decisionCycles';

// ==============================|| PIPELINE STEPS ||============================== //
//
// Sprint Next steps 5.13 — the starting step, among the steps the backend
// creates for a new cycle (PIPELINE_STEPS_CONFIG, decision_cycles/constants.py:
// QUALIFICATION → CLOSING), read from the ONE front constant
// (api/accounts/decisionCycles) — no local list any more. Chosen in pills: the
// scope pills' single-choice pattern (ScopeDepartmentsField — ClickablePill,
// active + pressed).
//
// Lot 3 / 10 (TD-305) — the drawer's validation pattern: the name is an
// InlineEditableValue (read → click → edit, the required message under it — as
// the summary of the Edit*Content drawers) and the form is validated /
// discarded by THE shared ✓/✗ row (components/drawer/ConfirmCancelActions,
// as EditTechStackContent's start-year editor). ✗ calls onCancel when given;
// without it (the conversion: the cycle is mandatory) ✗ discards the draft.

// ==============================|| VALIDATION SCHEMA ||============================== //

const validationSchema = Yup.object({
  name: Yup.string()
    .required('Cycle name is required')
    .max(255, 'Name must be at most 255 characters'),
  step_stage: Yup.string()
    .required('Pipeline step is required')
});

// ==============================|| INLINE CYCLE FORM ||============================== //

export default function InlineCycleForm({ onSave, onCancel }) {
  const formik = useFormik({
    initialValues: {
      name: '',
      step_stage: PIPELINE_STEPS_ORDER[0]
    },
    validationSchema,
    onSubmit: (values) => {
      onSave({
        name: values.name.trim(),
        is_active: true,
        step_stage: values.step_stage
      });
    }
  });

  const { values, errors, touched, handleSubmit, setFieldValue, resetForm } = formik;
  const nameError = touched.name && errors.name;

  return (
    <Box sx={{ pt: 1, pb: 2 }}>
      <Stack spacing={2}>
        <Typography variant="body2" color="text.secondary">
          Quick create a new decision cycle
        </Typography>
        <InlineEditableValue
          name="cycle_name"
          label="Cycle name"
          value={values.name}
          onChange={(v) => setFieldValue('name', v)}
          placeholder="Required"
          error={Boolean(nameError)}
          helperText={nameError || undefined}
        />
        {/* The starting step — one pill per step, a single choice. */}
        <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap data-testid="stage-pills">
          {PIPELINE_STEPS_ORDER.map((stage) => {
            const isActive = values.step_stage === stage;
            return (
              <ClickablePill
                key={stage}
                data-testid={`stage-pill-${stage}`}
                active={isActive}
                pressed={isActive}
                onClick={() => setFieldValue('step_stage', stage)}
                label={PIPELINE_STEP_LABELS[stage]}
              />
            );
          })}
        </Stack>
        <ConfirmCancelActions
          onConfirm={handleSubmit}
          onCancel={onCancel ?? (() => resetForm())}
          testIdBase="inline-cycle"
          label="new cycle"
        />
      </Stack>
    </Box>
  );
}

InlineCycleForm.propTypes = {
  onSave: PropTypes.func.isRequired,
  /** ✗ — optional: absent when the cycle is mandatory (the conversion), ✗
      then discards the draft. */
  onCancel: PropTypes.func
};
