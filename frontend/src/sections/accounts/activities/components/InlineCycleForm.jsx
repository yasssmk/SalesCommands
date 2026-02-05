import PropTypes from 'prop-types';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

// third-party
import { useFormik } from 'formik';
import * as Yup from 'yup';

// icons
import CloseOutlined from '@ant-design/icons/CloseOutlined';

// ==============================|| PIPELINE STEPS (FIXED) ||============================== //

export const PIPELINE_STEPS = [
  { value: 'QUALIFICATION', label: 'Qualification' },
  { value: 'TECHNICAL_FIT', label: 'Technical Fit' },
  { value: 'SOLUTION_VALIDATION', label: 'Solution Validation' },
  { value: 'BUSINESS_CASE', label: 'Business Case' },
  { value: 'CLOSING', label: 'Closing' },
  { value: 'IMPLEMENTATION', label: 'Implementation' },
  { value: 'GO_LIVE', label: 'Go Live' },
];

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
      step_stage: 'QUALIFICATION'
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

  const { values, errors, touched, handleChange, handleBlur, handleSubmit } = formik;

  return (
    <Box sx={{ pt: 1, pb: 2 }}>
      <Stack spacing={2}>
        <Typography variant="body2" color="text.secondary">
          Quick create a new decision cycle
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6}>
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
          </Grid>
          <Grid item xs={12} sm={6}>
            <Select
              fullWidth
              id="step_stage"
              name="step_stage"
              value={values.step_stage}
              onChange={handleChange}
              onBlur={handleBlur}
              displayEmpty
            >
              {PIPELINE_STEPS.map((step) => (
                <MenuItem key={step.value} value={step.value}>
                  {step.label}
                </MenuItem>
              ))}
            </Select>
          </Grid>
        </Grid>
        <Stack direction="row" spacing={1} justifyContent="flex-end">
          <Button type="button" size="small" onClick={onCancel} startIcon={<CloseOutlined />}>
            Cancel
          </Button>
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
  onCancel: PropTypes.func.isRequired
};