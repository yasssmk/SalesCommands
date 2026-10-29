import PropTypes from 'prop-types';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

// third-party
import { useFormik } from 'formik';
import * as Yup from 'yup';

// icons
import CloseOutlined from '@ant-design/icons/CloseOutlined';

// project imports
import ClickablePill from 'components/chips/ClickablePill';
import { PIPELINE_STEPS_ORDER, PIPELINE_STEP_LABELS } from 'api/accounts/decisionCycles';

// ==============================|| PIPELINE STEPS ||============================== //
//
// Sprint Next steps 5.13 — the starting step, among the steps the backend
// creates for a new cycle (PIPELINE_STEPS_CONFIG, decision_cycles/constants.py:
// QUALIFICATION → CLOSING), read from the ONE front constant
// (api/accounts/decisionCycles) — no local list any more. Chosen in pills: the
// scope pills' single-choice pattern (ScopeDepartmentsField — ClickablePill,
// active + pressed).

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

  const { values, errors, touched, handleChange, handleBlur, handleSubmit, setFieldValue } = formik;

  return (
    <Box sx={{ pt: 1, pb: 2 }}>
      <Stack spacing={2}>
        <Typography variant="body2" color="text.secondary">
          Quick create a new decision cycle
        </Typography>
        <TextField
          fullWidth
          id="name"
          name="name"
          value={values.name}
          onChange={handleChange}
          onBlur={handleBlur}
          placeholder="Cycle name *"
          error={Boolean(touched.name && errors.name)}
          helperText={touched.name && errors.name}
          autoFocus
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
        <Stack direction="row" spacing={1} justifyContent="flex-end">
          {onCancel && (
            <Button type="button" size="small" onClick={onCancel} startIcon={<CloseOutlined />}>
              Cancel
            </Button>
          )}
          <Button type="button" size="small" variant="contained" onClick={handleSubmit}>
            Create Cycle
          </Button>
        </Stack>
      </Stack>
    </Box>
  );
}

InlineCycleForm.propTypes = {
  onSave: PropTypes.func.isRequired,
  /** Optional: no Cancel when the cycle is mandatory (the conversion). */
  onCancel: PropTypes.func
};
