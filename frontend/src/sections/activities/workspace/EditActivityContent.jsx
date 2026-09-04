// frontend/src/sections/activities/workspace/EditActivityContent.jsx
//
// SE-b — the Activity EDIT drawer, rebuilt on the shared DrawerContentLayout +
// InlineEditableValue. It is a SHELL-LESS node injected into the WorkspaceDrawer
// coque. ONE content box holds the field groups, separated by internal hairline
// filets; each field edits on DOUBLE-CLICK (no textual "Edit", no per-group
// title). A single GLOBAL Save PATCHes the modified CONTENT fields via
// updateActivity; Cancel closes the coque.
//
// Groups: (1) Title + Type · (2) Date & time (scheduled|due exclusive toggle,
// mechanics cloned from UnifiedDateSection) · (3) Objective + Description ·
// (4) People — a READ-ONLY placeholder here, made editable in SE-c.
//
// Formik + Yup (title required, at-least-one-date); no hardcoded hex/px.

"use client";

import PropTypes from "prop-types";
import { useState } from "react";

import { useFormik } from "formik";
import * as Yup from "yup";
import dayjs from "dayjs";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { TimePicker } from "@mui/x-date-pickers/TimePicker";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";

// Project
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import { updateActivity, ACTIVITY_TYPES, ACTIVITY_TYPE_LABELS } from "api/accounts/activities";
import { displaySuccessSnackbar, displayErrorSnackbar } from "utils/displayError";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import InlineEditableValue from "components/drawer/InlineEditableValue";
import PersonRow from "components/display/PersonRow";

// ==============================|| VALIDATION ||============================== //

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
  },
  [["scheduled_date", "due_date"]],
);

// ==============================|| HELPERS ||============================== //

const TYPE_OPTIONS = Object.entries(ACTIVITY_TYPES).map(([key, value]) => ({
  value,
  label: ACTIVITY_TYPE_LABELS[key],
}));

function fmtDate(v) {
  return v ? dayjs(v).format("YYYY-MM-DD") : null;
}
function readDate(v) {
  return v ? dayjs(v).format("MMM D, YYYY") : null;
}
function readTime(t) {
  return t ? dayjs(t).format("h:mm A") : null;
}
function personName(p) {
  return p?.full_name || [p?.first_name, p?.last_name].filter(Boolean).join(" ") || p?.email || null;
}

// ==============================|| INTERNAL FILET ||============================== //

// The same hairline separator as the workspace header, used BETWEEN groups.
function Filet() {
  const aq = useTheme().aphoriQ;
  return (
    <Box
      data-testid="group-filet"
      sx={{
        borderTopStyle: "solid",
        borderTopWidth: aq.border.width.hairline,
        borderTopColor: aq.border.color,
      }}
    />
  );
}

// ==============================|| DATE GROUP ||============================== //

// Read: label ("Scheduled" / "Due date") + the current date (+time). DOUBLE-CLICK
// flips to an inline toggle (scheduled|due, exclusive) + the active picker(s).
// Switching the toggle clears the OTHER date (and scheduled_time when leaving
// scheduled) — mechanics cloned from UnifiedDateSection.
function DateGroup({ values, setFieldValue }) {
  const aq = useTheme().aphoriQ;
  const [editing, setEditing] = useState(false);
  const [mode, setMode] = useState(values.scheduled_date || !values.due_date ? "scheduled" : "due");

  const handleMode = (_e, val) => {
    if (!val) return;
    setMode(val);
    if (val === "due") {
      setFieldValue("scheduled_date", null);
      setFieldValue("scheduled_time", null);
    } else {
      setFieldValue("due_date", null);
    }
  };

  if (editing) {
    const pickerLabel = mode === "scheduled" ? "Scheduled date" : "Due date";
    return (
      <LocalizationProvider dateAdapter={AdapterDayjs}>
        <Stack spacing={1.5}>
          <ToggleButtonGroup value={mode} exclusive onChange={handleMode} size="small">
            <ToggleButton value="scheduled">Scheduled</ToggleButton>
            <ToggleButton value="due">Due Date</ToggleButton>
          </ToggleButtonGroup>

          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <DatePicker
                label={pickerLabel}
                value={mode === "scheduled" ? values.scheduled_date : values.due_date}
                onChange={(v) => {
                  if (mode === "scheduled") {
                    setFieldValue("scheduled_date", v);
                    if (!v) setFieldValue("scheduled_time", null);
                  } else {
                    setFieldValue("due_date", v);
                  }
                }}
                slotProps={{ textField: { fullWidth: true, size: "small" } }}
              />
            </Box>
            {mode === "scheduled" && (
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <TimePicker
                  label="Scheduled time"
                  value={values.scheduled_time}
                  onChange={(v) => setFieldValue("scheduled_time", v)}
                  disabled={!values.scheduled_date}
                  slotProps={{ textField: { fullWidth: true, size: "small" } }}
                />
              </Box>
            )}
          </Stack>
        </Stack>
      </LocalizationProvider>
    );
  }

  const isScheduled = Boolean(values.scheduled_date) || !values.due_date;
  const dateVal = isScheduled ? readDate(values.scheduled_date) : readDate(values.due_date);
  const timeVal = isScheduled ? readTime(values.scheduled_time) : null;
  const display = dateVal ? (timeVal ? `${dateVal} · ${timeVal}` : dateVal) : null;

  return (
    <Box>
      <Typography variant="caption" sx={{ color: aq.text.muted, display: "block", mb: 0.25 }}>
        {isScheduled ? "Scheduled" : "Due date"}
      </Typography>
      <Box
        data-testid="inline-read-date"
        onDoubleClick={() => setEditing(true)}
        sx={{ cursor: "pointer", py: 0.25 }}
      >
        {display ? (
          <Typography variant="body2" color="text.primary">
            {display}
          </Typography>
        ) : (
          <Typography variant="body2" sx={{ color: aq.text.subtle, fontStyle: "italic" }}>
            No date set
          </Typography>
        )}
      </Box>
    </Box>
  );
}

DateGroup.propTypes = { values: PropTypes.object.isRequired, setFieldValue: PropTypes.func.isRequired };

// ==============================|| PEOPLE PLACEHOLDER (SE-c) ||============================== //

// Read-only for now — owner / invited / contacts. SE-c replaces this with the
// editable owner slot + removable invited/contacts + AsyncSelects.
function PeoplePlaceholder({ activity }) {
  const aq = useTheme().aphoriQ;
  const owner = personName(activity?.owner_detail);
  const invited = activity?.invited_users_detail || [];
  const contacts = activity?.contacts_detail || [];
  const caption = (t) => (
    <Typography variant="caption" sx={{ color: aq.text.muted, display: "block", mb: 0.25 }}>
      {t}
    </Typography>
  );
  return (
    <Stack data-testid="people-placeholder" spacing={1.5}>
      <Box>
        {caption("Owner")}
        {owner ? <PersonRow name={owner} suffix="owner" /> : null}
      </Box>
      <Box>
        {caption("Invited users")}
        {invited.length ? invited.map((u) => <PersonRow key={u.id} name={personName(u)} />) : (
          <Typography variant="body2" sx={{ color: aq.text.subtle, fontStyle: "italic" }}>None</Typography>
        )}
      </Box>
      <Box>
        {caption("Contacts")}
        {contacts.length ? contacts.map((c) => <PersonRow key={c.id} name={personName(c)} />) : (
          <Typography variant="body2" sx={{ color: aq.text.subtle, fontStyle: "italic" }}>None</Typography>
        )}
      </Box>
    </Stack>
  );
}

PeoplePlaceholder.propTypes = { activity: PropTypes.object.isRequired };

// ==============================|| EDIT ACTIVITY CONTENT ||============================== //

export default function EditActivityContent({ activity, onSaved }) {
  const { closeDrawer } = useWorkspaceDrawer();

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
    },
    onSubmit: async (values, { setSubmitting }) => {
      const payload = {
        title: values.title.trim(),
        activity_type: values.activity_type,
        scheduled_date: fmtDate(values.scheduled_date),
        scheduled_time:
          values.scheduled_date && values.scheduled_time
            ? dayjs(values.scheduled_time).format("HH:mm:ss")
            : null,
        due_date: fmtDate(values.due_date),
        call_to_action: values.call_to_action?.trim() || null,
        description: values.description?.trim() || null,
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

  const { values, errors, setFieldValue } = formik;

  return (
    <DrawerContentLayout
      title="Edit activity"
      onSave={formik.handleSubmit}
      onCancel={() => closeDrawer()}
      saveDisabled={!formik.isValid || !formik.dirty || formik.isSubmitting}
    >
      <Stack spacing={1.5}>
        {/* (1) Title + Type */}
        <InlineEditableValue
          name="title"
          label="Title"
          value={values.title}
          onChange={(v) => setFieldValue("title", v)}
          placeholder="Untitled"
          error={Boolean(errors.title)}
          helperText={errors.title}
        />
        <InlineEditableValue
          name="type"
          label="Type"
          type="select"
          options={TYPE_OPTIONS}
          value={values.activity_type}
          onChange={(v) => setFieldValue("activity_type", v)}
        />

        <Filet />

        {/* (2) Date & time */}
        <DateGroup values={values} setFieldValue={setFieldValue} />
        {Boolean(errors.scheduled_date) && (
          <Typography variant="caption" color="error">
            {errors.scheduled_date}
          </Typography>
        )}

        <Filet />

        {/* (3) Objective + Description */}
        <InlineEditableValue
          name="objective"
          label="Objective"
          value={values.call_to_action}
          onChange={(v) => setFieldValue("call_to_action", v)}
          placeholder="No objective set"
        />
        <InlineEditableValue
          name="description"
          label="Description"
          type="textarea"
          value={values.description}
          onChange={(v) => setFieldValue("description", v)}
          placeholder="No description added"
        />

        <Filet />

        {/* (4) People — read-only placeholder (SE-c) */}
        <PeoplePlaceholder activity={activity} />
      </Stack>
    </DrawerContentLayout>
  );
}

EditActivityContent.propTypes = {
  /** The activity to edit (its *_detail fields seed the values). */
  activity: PropTypes.object.isRequired,
  /** Optional callback fired after a successful save (before the coque closes). */
  onSaved: PropTypes.func,
};
