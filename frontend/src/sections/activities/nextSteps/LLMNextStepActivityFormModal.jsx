// frontend/src/sections/activities/nextSteps/LLMNextStepActivityFormModal.jsx

"use client";

import PropTypes from "prop-types";
import { useMemo, useEffect } from "react";

// MUI
import Autocomplete from "@mui/material/Autocomplete";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import FormControl from "@mui/material/FormControl";
import FormHelperText from "@mui/material/FormHelperText";
import IconButton from "@mui/material/IconButton";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

// Date pickers
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import dayjs from "dayjs";

// Formik + Yup
import { useFormik } from "formik";
import * as Yup from "yup";

// Icons
import { CloseOutlined } from "@ant-design/icons";

// Project imports
import {
  createActivity,
  ACTIVITY_TYPES,
  ACTIVITY_TYPE_LABELS,
} from "api/accounts/activities";
import { useGetContacts } from "api/businessData/contacts";
import {
  displayErrorSnackbar,
  displaySuccessSnackbar,
} from "utils/displayError";

// ==============================|| VALIDATION ||============================== //

const validationSchema = Yup.object(
  {
    title: Yup.string()
      .required("Title is required")
      .max(255, "Title must be at most 255 characters"),
    activity_type: Yup.string().required("Activity type is required"),
    scheduled_date: Yup.date()
      .nullable()
      .typeError("Please select a valid date")
      .when("due_date", {
        is: (dueDate) => !dueDate,
        then: (schema) =>
          schema.required("Scheduled date or due date is required"),
        otherwise: (schema) => schema.nullable(),
      }),
    due_date: Yup.date().nullable().typeError("Please select a valid date"),
    contact_ids: Yup.array().of(Yup.string()),
  },
  [["scheduled_date", "due_date"]],
);

// ==============================|| LLM NEXT STEP ACTIVITY FORM MODAL ||============================== //

export default function LLMNextStepActivityFormModal({
  open,
  onClose,
  onSuccess,
  signal,
  accountId,
}) {
  const isFromSignal = Boolean(signal);

  const { contacts, contactsLoading } = useGetContacts(
    open ? { filters: { account_id: accountId }, pageSize: 100 } : null,
  );

  const contactOptions = useMemo(() => {
    if (!contacts || contacts.length === 0) return [];
    return contacts.map((c) => ({
      id: c.id,
      label:
        `${c.first_name || ""} ${c.last_name || ""}`.trim() || c.email,
      email: c.email,
      job_title: c.job_title,
    }));
  }, [contacts]);

  const suggestedContactIds = useMemo(() => {
    if (!signal?.suggested_contacts) return [];
    return signal.suggested_contacts.map((c) => c.id);
  }, [signal]);

  const initialValues = useMemo(
    () => ({
      title: signal?.suggested_title || "",
      activity_type: signal?.suggested_activity_type || "MEETING",
      scheduled_date: signal?.suggested_due_date
        ? dayjs(signal.suggested_due_date)
        : null,
      due_date: null,
      contact_ids: suggestedContactIds,
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [signal?.id, open],
  );

  const formik = useFormik({
    initialValues,
    validationSchema,
    enableReinitialize: true,
    onSubmit: async (values) => {
      const payload = {
        title: values.title.trim(),
        activity_type: values.activity_type,
        account_id: accountId,
        contact_ids: values.contact_ids,
        scheduled_date: values.scheduled_date
          ? dayjs(values.scheduled_date).format("YYYY-MM-DD")
          : null,
        due_date: values.due_date
          ? dayjs(values.due_date).format("YYYY-MM-DD")
          : null,
      };

      if (isFromSignal && signal?.id) {
        payload.next_step_signal_id = signal.id;
      }

      const result = await createActivity(payload);

      if (result.success) {
        displaySuccessSnackbar(
          isFromSignal
            ? "Activity created from AI suggestion"
            : "Activity created",
        );
        onSuccess?.(result.data);
        onClose();
      } else {
        displayErrorSnackbar(result);
      }
    },
  });

  const { values, errors, touched, handleSubmit, setFieldValue, resetForm } =
    formik;

  useEffect(() => {
    if (open) {
      resetForm({ values: initialValues });
    }
  }, [open, initialValues, resetForm]);

  const selectedContacts = useMemo(() => {
    return contactOptions.filter((c) => values.contact_ids.includes(c.id));
  }, [contactOptions, values.contact_ids]);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      aria-labelledby="llm-nextstep-modal-title"
    >
      <DialogTitle id="llm-nextstep-modal-title" sx={{ pr: 6 }}>
        {isFromSignal ? "Convert to Activity" : "Create Activity"}
        <IconButton
          size="small"
          onClick={onClose}
          aria-label="Close"
          sx={{
            position: "absolute",
            right: 16,
            top: 14,
            color: "text.secondary",
          }}
        >
          <CloseOutlined style={{ fontSize: 14 }} />
        </IconButton>
      </DialogTitle>

      <Divider />

      <DialogContent sx={{ pt: 2.5, pb: 3 }}>
        {contactsLoading ? (
          <Box display="flex" justifyContent="center" py={4}>
            <CircularProgress size={24} />
          </Box>
        ) : (
          <Box component="form" onSubmit={handleSubmit}>
            <Stack spacing={2.5}>
              {/* Source quote context */}
              {isFromSignal && signal?.source_quote && (
                <Box
                  sx={{
                    borderLeft: 3,
                    borderColor: "warning.main",
                    pl: 1.5,
                    py: 0.5,
                    bgcolor: "warning.lighter",
                    borderRadius: 1,
                  }}
                >
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    fontWeight={600}
                  >
                    AI Rationale
                  </Typography>
                  <Typography
                    variant="body2"
                    fontStyle="italic"
                    color="text.secondary"
                  >
                    &ldquo;{signal.source_quote}&rdquo;
                  </Typography>
                </Box>
              )}

              {/* Title */}
              <TextField
                name="title"
                label="Title"
                value={values.title}
                onChange={formik.handleChange}
                onBlur={formik.handleBlur}
                error={touched.title && Boolean(errors.title)}
                helperText={touched.title && errors.title}
                fullWidth
                required
              />

              {/* Activity Type */}
              <FormControl
                fullWidth
                required
                error={
                  touched.activity_type && Boolean(errors.activity_type)
                }
              >
                <InputLabel id="nextstep-act-type-label">
                  Activity type
                </InputLabel>
                <Select
                  labelId="nextstep-act-type-label"
                  name="activity_type"
                  value={values.activity_type}
                  label="Activity type"
                  onChange={formik.handleChange}
                  onBlur={formik.handleBlur}
                >
                  {Object.entries(ACTIVITY_TYPES).map(([key, value]) => (
                    <MenuItem key={key} value={value}>
                      {ACTIVITY_TYPE_LABELS[key] || key}
                    </MenuItem>
                  ))}
                </Select>
                {touched.activity_type && errors.activity_type && (
                  <FormHelperText>{errors.activity_type}</FormHelperText>
                )}
              </FormControl>

              {/* Scheduled Date */}
              <LocalizationProvider dateAdapter={AdapterDayjs}>
                <DatePicker
                  label="Scheduled date"
                  value={values.scheduled_date}
                  onChange={(val) => setFieldValue("scheduled_date", val)}
                  slotProps={{
                    textField: {
                      fullWidth: true,
                      error:
                        touched.scheduled_date &&
                        Boolean(errors.scheduled_date),
                      helperText:
                        touched.scheduled_date && errors.scheduled_date,
                      onBlur: formik.handleBlur,
                      name: "scheduled_date",
                    },
                  }}
                />
              </LocalizationProvider>

              {/* Contacts */}
              <Autocomplete
                multiple
                options={contactOptions}
                getOptionLabel={(option) => option.label || ""}
                value={selectedContacts}
                onChange={(_, newValue) => {
                  setFieldValue(
                    "contact_ids",
                    newValue.map((v) => v.id),
                  );
                }}
                isOptionEqualToValue={(option, value) =>
                  option.id === value.id
                }
                renderOption={(props, option) => (
                  <li {...props} key={option.id}>
                    <Stack>
                      <Typography variant="body2">{option.label}</Typography>
                      {option.job_title && (
                        <Typography variant="caption" color="text.secondary">
                          {option.job_title}
                        </Typography>
                      )}
                    </Stack>
                  </li>
                )}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Contacts"
                    placeholder="Select contacts"
                    error={
                      touched.contact_ids && Boolean(errors.contact_ids)
                    }
                    helperText={touched.contact_ids && errors.contact_ids}
                  />
                )}
              />

              {/* Actions */}
              <Stack direction="row" spacing={1.5} justifyContent="flex-end">
                <Button variant="outlined" onClick={onClose}>
                  Cancel
                </Button>
                <Button type="submit" variant="contained">
                  {isFromSignal ? "Create Activity" : "Create"}
                </Button>
              </Stack>
            </Stack>
          </Box>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ==============================|| PROP TYPES ||============================== //

LLMNextStepActivityFormModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onSuccess: PropTypes.func,
  signal: PropTypes.shape({
    id: PropTypes.string,
    suggested_title: PropTypes.string,
    suggested_activity_type: PropTypes.string,
    suggested_due_date: PropTypes.string,
    suggested_contacts: PropTypes.arrayOf(
      PropTypes.shape({
        id: PropTypes.string,
        first_name: PropTypes.string,
        last_name: PropTypes.string,
      }),
    ),
    source_quote: PropTypes.string,
  }),
  accountId: PropTypes.string.isRequired,
};
