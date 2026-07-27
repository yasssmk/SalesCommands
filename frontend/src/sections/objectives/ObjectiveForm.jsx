// frontend/src/sections/objectives/ObjectiveForm.jsx
//
// Create / edit form for a personal objective. Formik + Yup, mounted in a modal
// by ObjectiveModal — mirrors the territories FormTerritoryAdd pattern
// (FormikProvider + Form, onSubmit -> api helper -> snackbar -> closeModal).

import PropTypes from 'prop-types';
import { useState } from 'react';
import dayjs from 'dayjs';

import Button from '@mui/material/Button';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import FormControl from '@mui/material/FormControl';
import FormHelperText from '@mui/material/FormHelperText';
import Grid from '@mui/material/Grid';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';

import { useFormik, Form, FormikProvider } from 'formik';
import * as Yup from 'yup';

import { useGetCampaigns } from 'api/campaigns/campaigns';
import { createObjective, updateObjective } from 'api/objectives/objectives';
import { METRICS } from './metricLabels';
import { displaySuccessSnackbar } from 'utils/displayError';
import { handleFormikError } from 'utils/formErrorHandler';

const NONE = '';

const Schema = Yup.object().shape({
  metric: Yup.string().oneOf(METRICS.map((m) => m.value), 'Invalid metric').required('Metric is required'),
  target_value: Yup.number().typeError('Target must be a number').positive('Target must be positive').required('Target is required'),
  period_start: Yup.string().required('Start date is required'),
  period_end: Yup.string()
    .required('End date is required')
    .test('after-start', 'End date must be on or after start date', function (end) {
      const { period_start } = this.parent;
      if (!end || !period_start) return true;
      return !dayjs(end).isBefore(dayjs(period_start), 'day');
    }),
  source_campaign: Yup.string().nullable(),
});

function buildInitialValues(objective) {
  return {
    metric: objective?.metric || NONE,
    target_value: objective?.target_value ?? '',
    period_start: objective?.period_start || NONE,
    period_end: objective?.period_end || NONE,
    // source_campaign in the payload is the campaign id (or null); the form holds
    // '' for "global".
    source_campaign: objective?.source_campaign || NONE,
  };
}

export default function ObjectiveForm({ objective, closeModal }) {
  const isEdit = Boolean(objective?.id);
  const [submitting, setSubmitting] = useState(false);
  const { campaigns = [] } = useGetCampaigns({ page: 1, pageSize: 100 });

  const formik = useFormik({
    initialValues: buildInitialValues(objective),
    validationSchema: Schema,
    enableReinitialize: false,
    onSubmit: async (values) => {
      setSubmitting(true);
      try {
        const payload = {
          metric: values.metric,
          target_value: Number(values.target_value),
          period_start: values.period_start,
          period_end: values.period_end,
          // empty select -> null = global objective; set = declined on a campaign.
          source_campaign: values.source_campaign || null,
        };
        const result = isEdit
          ? await updateObjective(objective.id, payload)
          : await createObjective(payload);

        if (result.success) {
          displaySuccessSnackbar(isEdit ? 'Objective updated' : 'Objective created');
          closeModal?.();
        } else {
          handleFormikError(result, formik);
        }
      } catch (err) {
        handleFormikError(err, formik);
      } finally {
        setSubmitting(false);
      }
    },
  });

  const { errors, touched, handleSubmit, getFieldProps, values, setFieldValue } = formik;

  const setDate = (field) => (value) =>
    setFieldValue(field, value ? dayjs(value).format('YYYY-MM-DD') : NONE);

  return (
    <FormikProvider value={formik}>
      <Form autoComplete="off" noValidate onSubmit={handleSubmit}>
        <DialogTitle>{isEdit ? 'Edit Objective' : 'New Objective'}</DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <FormControl fullWidth error={Boolean(touched.metric && errors.metric)}>
                <InputLabel id="objective-metric-label">Metric</InputLabel>
                <Select
                  labelId="objective-metric-label"
                  label="Metric"
                  inputProps={{ 'aria-label': 'Metric' }}
                  {...getFieldProps('metric')}
                >
                  {METRICS.map((m) => (
                    <MenuItem key={m.value} value={m.value}>
                      {m.label}
                    </MenuItem>
                  ))}
                </Select>
                {touched.metric && errors.metric && <FormHelperText>{errors.metric}</FormHelperText>}
              </FormControl>
            </Grid>

            <Grid item xs={12}>
              <TextField
                fullWidth
                type="number"
                label="Target value"
                inputProps={{ 'aria-label': 'Target value' }}
                {...getFieldProps('target_value')}
                error={Boolean(touched.target_value && errors.target_value)}
                helperText={touched.target_value && errors.target_value}
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <LocalizationProvider dateAdapter={AdapterDayjs}>
                <DatePicker
                  label="Start date"
                  value={values.period_start ? dayjs(values.period_start) : null}
                  onChange={setDate('period_start')}
                  slotProps={{
                    textField: {
                      fullWidth: true,
                      error: Boolean(touched.period_start && errors.period_start),
                      helperText: touched.period_start && errors.period_start,
                      inputProps: { 'aria-label': 'Start date' },
                    },
                  }}
                />
              </LocalizationProvider>
            </Grid>

            <Grid item xs={12} sm={6}>
              <LocalizationProvider dateAdapter={AdapterDayjs}>
                <DatePicker
                  label="End date"
                  value={values.period_end ? dayjs(values.period_end) : null}
                  onChange={setDate('period_end')}
                  slotProps={{
                    textField: {
                      fullWidth: true,
                      error: Boolean(touched.period_end && errors.period_end),
                      helperText: touched.period_end && errors.period_end,
                      inputProps: { 'aria-label': 'End date' },
                    },
                  }}
                />
              </LocalizationProvider>
            </Grid>

            <Grid item xs={12}>
              <FormControl fullWidth>
                <InputLabel id="objective-campaign-label">Campaign (optional)</InputLabel>
                <Select
                  labelId="objective-campaign-label"
                  label="Campaign (optional)"
                  inputProps={{ 'aria-label': 'Campaign' }}
                  {...getFieldProps('source_campaign')}
                >
                  <MenuItem value={NONE}>
                    <em>Global (no campaign)</em>
                  </MenuItem>
                  {campaigns.map((c) => (
                    <MenuItem key={c.id} value={c.id}>
                      {c.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Stack direction="row" spacing={1}>
            <Button color="secondary" onClick={closeModal} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" variant="contained" disabled={submitting}>
              {isEdit ? 'Save' : 'Create'}
            </Button>
          </Stack>
        </DialogActions>
      </Form>
    </FormikProvider>
  );
}

ObjectiveForm.propTypes = {
  objective: PropTypes.object,
  closeModal: PropTypes.func,
};
