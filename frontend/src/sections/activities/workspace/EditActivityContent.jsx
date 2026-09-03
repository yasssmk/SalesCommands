// frontend/src/sections/activities/workspace/EditActivityContent.jsx
//
// S2c-1 — the Activity EDIT form, injected as a SHELL-LESS node into the shared
// WorkspaceDrawer coque via openDrawer(<EditActivityContent activity=… />). The
// coque already provides the drawer shell (close button + padded scroll body +
// width) — this node renders ONLY its section title, the form, and the actions,
// and closes via closeDrawer.
//
// Edits CONTENT fields only (PO-fixed scope): title, activity_type, scheduled
// date/time, due date, objective (call_to_action), description, owner, invited
// users, contacts. NO status, NO cycle/step. Formik + Yup, matching the project
// standard (ActivityModal's field patterns + date rule). Save PATCHes via
// updateActivity (which already revalidates SWR, so the header/Context refresh).
// Themed via aphoriQ/MUI — no hardcoded hex/px.

"use client";

import PropTypes from "prop-types";

import { useFormik } from "formik";
import * as Yup from "yup";
import dayjs from "dayjs";

// MUI
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import FormHelperText from "@mui/material/FormHelperText";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { TimePicker } from "@mui/x-date-pickers/TimePicker";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";

// Project
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import {
  updateActivity,
  ACTIVITY_TYPES,
  ACTIVITY_TYPE_LABELS,
} from "api/accounts/activities";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";
import AsyncUserSelect from "components/AsyncSelection/AsyncUserSelect";
import AsyncContactSelect from "components/AsyncSelection/AsyncContactSelect";

// ==============================|| VALIDATION ||============================== //

// Mirrors ActivityModal's date rule (serializers.py:1224-1230 — at least one of
// scheduled_date / due_date must remain) plus the min-1-contact backend rule.
const validationSchema = Yup.object(
  {
    title: Yup.string().trim().required("Title is required").max(255, "Title must be at most 255 characters"),
    activity_type: Yup.string().required("Activity type is required"),
    call_to_action: Yup.string().max(500, "Objective must be at most 500 characters").nullable(),
    description: Yup.string().max(2000, "Description must be at most 2000 characters").nullable(),
    scheduled_date: Yup.date()
      .nullable()
      .typeError("Please select a valid date")
      .when("due_date", {
        is: (dueDate) => !dueDate,
        then: (schema) => schema.required("A scheduled date or a due date is required"),
        otherwise: (schema) => schema.nullable(),
      }),
    due_date: Yup.date().nullable().typeError("Please select a valid date"),
    contacts: Yup.array().min(1, "At least one contact is required"),
  },
  [["scheduled_date", "due_date"]],
);

// ==============================|| HELPERS ||============================== //

function fmtDate(v) {
  return v ? dayjs(v).format("YYYY-MM-DD") : null;
}

// ==============================|| EDIT ACTIVITY CONTENT ||============================== //

export default function EditActivityContent({ activity, onSaved }) {
  const { closeDrawer } = useWorkspaceDrawer();
  const accountId = activity?.account_detail?.id || activity?.account || null;

  const formik = useFormik({
    enableReinitialize: true,
    validationSchema,
    initialValues: {
      title: activity?.title || "",
      activity_type: activity?.activity_type || "",
      scheduled_date: activity?.scheduled_date ? dayjs(activity.scheduled_date) : null,
      scheduled_time: activity?.scheduled_time ? dayjs(`2000-01-01T${activity.scheduled_time}`) : null,
      due_date: activity?.due_date ? dayjs(activity.due_date) : null,
      call_to_action: activity?.call_to_action || "",
      description: activity?.description || "",
      owner: activity?.owner_detail || null,
      invited: activity?.invited_users_detail || [],
      contacts: activity?.contacts_detail || [],
    },
    onSubmit: async (values, { setSubmitting }) => {
      const payload = {
        title: values.title.trim(),
        activity_type: values.activity_type,
        scheduled_date: fmtDate(values.scheduled_date),
        // time only survives when a scheduled date does
        scheduled_time:
          values.scheduled_date && values.scheduled_time
            ? dayjs(values.scheduled_time).format("HH:mm:ss")
            : null,
        due_date: fmtDate(values.due_date),
        call_to_action: values.call_to_action?.trim() || null,
        description: values.description?.trim() || null,
        owner_id: values.owner?.id ?? null,
        invited_user_ids: (values.invited || []).map((u) => u.id),
        contact_ids: (values.contacts || []).map((c) => c.id),
      };
      try {
        const result = await updateActivity(activity.id, payload);
        if (result?.success) {
          displaySuccessSnackbar("Activity updated");
          onSaved?.();
          closeDrawer();
        } else {
          displayErrorSnackbar(result);
        }
      } catch (err) {
        displayErrorSnackbar(err);
      } finally {
        setSubmitting(false);
      }
    },
  });

  const { values, errors, touched, handleChange, handleBlur, setFieldValue, setFieldTouched } = formik;

  const fieldError = (name) => touched[name] && errors[name];

  return (
    <Stack spacing={2} component="form" onSubmit={formik.handleSubmit} noValidate>
      <Typography variant="subtitle2" color="text.primary" sx={{ fontWeight: "bold" }}>
        Edit activity
      </Typography>

      {/* Title */}
      <Stack spacing={0.5}>
        <InputLabel htmlFor="title" required>
          Title
        </InputLabel>
        <TextField
          id="title"
          name="title"
          fullWidth
          value={values.title}
          onChange={handleChange}
          onBlur={handleBlur}
          error={Boolean(fieldError("title"))}
          helperText={fieldError("title") || " "}
        />
      </Stack>

      {/* Type */}
      <Stack spacing={0.5}>
        <InputLabel htmlFor="activity_type" required>
          Type
        </InputLabel>
        <Select
          id="activity_type"
          name="activity_type"
          fullWidth
          value={values.activity_type}
          onChange={handleChange}
          onBlur={handleBlur}
          error={Boolean(fieldError("activity_type"))}
        >
          {Object.entries(ACTIVITY_TYPES).map(([key, value]) => (
            <MenuItem key={key} value={value}>
              {ACTIVITY_TYPE_LABELS[key]}
            </MenuItem>
          ))}
        </Select>
      </Stack>

      {/* Dates */}
      <LocalizationProvider dateAdapter={AdapterDayjs}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
          <Stack spacing={0.5} sx={{ flex: 1 }}>
            <InputLabel>Scheduled date</InputLabel>
            <DatePicker
              value={values.scheduled_date}
              onChange={(v) => {
                setFieldValue("scheduled_date", v);
                setFieldTouched("scheduled_date", true, false);
                if (!v) setFieldValue("scheduled_time", null);
              }}
              slotProps={{ textField: { fullWidth: true } }}
            />
          </Stack>
          <Stack spacing={0.5} sx={{ flex: 1 }}>
            <InputLabel>Scheduled time</InputLabel>
            <TimePicker
              value={values.scheduled_time}
              onChange={(v) => setFieldValue("scheduled_time", v)}
              disabled={!values.scheduled_date}
              slotProps={{ textField: { fullWidth: true } }}
            />
          </Stack>
          <Stack spacing={0.5} sx={{ flex: 1 }}>
            <InputLabel>Due date</InputLabel>
            <DatePicker
              value={values.due_date}
              onChange={(v) => {
                setFieldValue("due_date", v);
                setFieldTouched("due_date", true, false);
              }}
              slotProps={{ textField: { fullWidth: true } }}
            />
          </Stack>
        </Stack>
      </LocalizationProvider>
      {Boolean(fieldError("scheduled_date")) && (
        <FormHelperText error>{errors.scheduled_date}</FormHelperText>
      )}

      {/* Objective */}
      <Stack spacing={0.5}>
        <InputLabel htmlFor="call_to_action">Objective</InputLabel>
        <TextField
          id="call_to_action"
          name="call_to_action"
          fullWidth
          value={values.call_to_action}
          onChange={handleChange}
          onBlur={handleBlur}
          error={Boolean(fieldError("call_to_action"))}
          helperText={fieldError("call_to_action") || " "}
        />
      </Stack>

      {/* Description */}
      <Stack spacing={0.5}>
        <InputLabel htmlFor="description">Description</InputLabel>
        <TextField
          id="description"
          name="description"
          fullWidth
          multiline
          minRows={3}
          value={values.description}
          onChange={handleChange}
          onBlur={handleBlur}
          error={Boolean(fieldError("description"))}
          helperText={fieldError("description") || " "}
        />
      </Stack>

      {/* Owner */}
      <Stack spacing={0.5}>
        <InputLabel>Owner</InputLabel>
        <AsyncUserSelect
          value={values.owner}
          onChange={(v) => setFieldValue("owner", v)}
          label=""
          placeholder="Search a user…"
        />
      </Stack>

      {/* Invited users */}
      <Stack spacing={0.5}>
        <InputLabel>Invited users</InputLabel>
        <AsyncUserSelect
          multiple
          value={values.invited}
          onChange={(v) => setFieldValue("invited", v || [])}
          label=""
          placeholder="Search users…"
        />
      </Stack>

      {/* Contacts */}
      <Stack spacing={0.5}>
        <InputLabel required>Contacts</InputLabel>
        <AsyncContactSelect
          multiple
          value={values.contacts}
          onChange={(v) => setFieldValue("contacts", v || [])}
          filters={{ account_id: accountId }}
          label=""
          placeholder="Search contacts…"
          error={Boolean(fieldError("contacts"))}
          helperText={fieldError("contacts") || undefined}
        />
        {Boolean(fieldError("contacts")) && (
          <FormHelperText error>{errors.contacts}</FormHelperText>
        )}
      </Stack>

      {/* Actions */}
      <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 1, pt: 1 }}>
        <Button variant="text" color="inherit" onClick={() => closeDrawer()}>
          Cancel
        </Button>
        <Button
          type="submit"
          variant="contained"
          disabled={!formik.isValid || !formik.dirty || formik.isSubmitting}
        >
          Save
        </Button>
      </Box>
    </Stack>
  );
}

EditActivityContent.propTypes = {
  /** The activity to edit (its *_detail fields seed the initial values). */
  activity: PropTypes.object.isRequired,
  /** Optional callback fired after a successful save (before the coque closes). */
  onSaved: PropTypes.func,
};
