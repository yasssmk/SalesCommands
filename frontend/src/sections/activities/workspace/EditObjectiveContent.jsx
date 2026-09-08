// frontend/src/sections/activities/workspace/EditObjectiveContent.jsx
//
// SIG-5d* — the Objective EDIT drawer content. It keeps the ORIGINAL
// InlineObjectiveForm structure — the 3 SectionHeaders with their exact
// subtitles and the "Domain × Dimension" recap — but the fields are
// InlineEditableValue (read → double-click → inline edit, uniform with
// edit-activity / edit-contact), on DrawerContentLayout (global Save/Cancel).
//
// Differences vs the original form:
//   (a) scope block → the shared ObjectiveScopePill (Company / Department). When
//       DEPARTMENT the ORIGINAL MUI "Target Department *" Select is rendered
//       (mono-department — Objective is a single-FK scope, not M2M).
//   (b) source_quote is an added, editable field in its own titled section.
//
// The coque owns the "Edit objective" title (passed to openDrawer) — this content
// does NOT set a DrawerContentLayout title, so it never shows twice (same as
// EditContactContent). Save PATCHes via the existing generic updateSignal(
// "objective", id, patch). Theme tokens; the only literal px are copied verbatim
// from the original SectionHeader chip to stay pixel-faithful.
//
// InlineEditableValue supports text / textarea / select only (reused untouched),
// so target_date is an InlineEditableValue text field (ISO date string).

"use client";

import PropTypes from "prop-types";
import { useMemo, useState, useRef } from "react";

import { useFormik } from "formik";
import * as Yup from "yup";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Divider from "@mui/material/Divider";
import FormControl from "@mui/material/FormControl";
import FormHelperText from "@mui/material/FormHelperText";
import IconButton from "@mui/material/IconButton";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import CheckOutlined from "@ant-design/icons/CheckOutlined";
import CloseOutlined from "@ant-design/icons/CloseOutlined";

// Project
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import { updateSignal, useGetSignalChoices } from "api/signals/signals";
import { useGetContactChoices } from "api/businessData/contacts";
import { displaySuccessSnackbar, displayErrorSnackbar } from "utils/displayError";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import SectionHeader from "components/display/SectionHeader";
import InlineEditableValue from "components/drawer/InlineEditableValue";
import ObjectiveScopePill from "components/signals/ObjectiveScopePill";
import { OBJECTIVE_SCOPE } from "utils/objectiveScope";

// Date picker — the project's standard component (@mui/x-date-pickers + dayjs),
// same as EditActivityContent / OutcomeDrawerContent.
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import dayjs from "dayjs";

// ==============================|| HELPERS (reproduced from InlineObjectiveForm) ||=========== //

function resolveLabel(options, value) {
  if (!value || !options) return null;
  return options.find((o) => o.value === value)?.label ?? value;
}

// Target date — read row that reveals the project DatePicker ONLY on double-click,
// with ✓ (keep the draft) / ✗ (restore the pre-edit value), same interaction as
// EditActivityContent's scheduled-date field. Formik keeps the ISO "YYYY-MM-DD"
// string; the picker reads/writes a dayjs.
function TargetDateField({ value, onChange }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  const [editing, setEditing] = useState(false);
  const startRef = useRef(null);

  const startEdit = () => {
    startRef.current = value;
    setEditing(true);
  };
  const confirm = () => setEditing(false);
  const cancel = () => {
    onChange(startRef.current ?? "");
    setEditing(false);
  };

  if (editing) {
    return (
      <LocalizationProvider dateAdapter={AdapterDayjs}>
        <Stack spacing={1}>
          <DatePicker
            label="Target date"
            value={value ? dayjs(value) : null}
            onChange={(v) => onChange(v && v.isValid() ? v.format("YYYY-MM-DD") : "")}
            slotProps={{ textField: { fullWidth: true, size: "small" } }}
          />
          <Stack direction="row" justifyContent="flex-end" spacing={0.5}>
            <IconButton
              size="small"
              onClick={confirm}
              data-testid="target-date-confirm"
              aria-label="Confirm target date"
              sx={{ color: "success.main" }}
            >
              <CheckOutlined style={{ fontSize: theme.iconSizes.sm }} />
            </IconButton>
            <IconButton
              size="small"
              onClick={cancel}
              data-testid="target-date-cancel"
              aria-label="Discard target date"
              sx={{ color: "error.main" }}
            >
              <CloseOutlined style={{ fontSize: theme.iconSizes.sm }} />
            </IconButton>
          </Stack>
        </Stack>
      </LocalizationProvider>
    );
  }

  const display = value ? dayjs(value).format("D MMM YYYY") : null;
  return (
    <Box>
      <Typography variant="caption" sx={{ color: aq.text.muted, display: "block", mb: 0.25 }}>
        Target date
      </Typography>
      <Box
        data-testid="inline-read-target_date"
        onDoubleClick={startEdit}
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
TargetDateField.propTypes = {
  value: PropTypes.string,
  onChange: PropTypes.func.isRequired,
};

// ==============================|| VALIDATION (preserved from InlineObjectiveForm) ||=========== //

const validationSchema = Yup.object({
  summary: Yup.string()
    .trim()
    .min(10, "Summary must be at least 10 characters")
    .required("Summary is required"),
  what: Yup.string().required("Domain is required"),
  dimension: Yup.string().required("Dimension is required"),
  // DEPARTMENT scope requires a department; every other scope leaves it nullable
  // (so the error NEVER shows in Company). Mirror of the original + backend clean().
  target_department: Yup.string()
    .nullable()
    .when("scope_level", {
      is: OBJECTIVE_SCOPE.DEPARTMENT,
      then: (schema) => schema.required("Department objectives require a target department"),
      otherwise: (schema) => schema.nullable(),
    }),
  success_criteria: Yup.string().nullable(),
  target_date: Yup.string().nullable(),
  notes: Yup.string().nullable(),
  source_quote: Yup.string().nullable(),
});

// Normalise a target FK that may arrive as a compact {id,name} object (detail
// serializer) or a bare id — to the id string the form/patch use.
function fkId(v) {
  if (v == null) return "";
  return typeof v === "object" ? v.id ?? "" : v;
}

// ==============================|| EDIT OBJECTIVE CONTENT ||============================== //

export default function EditObjectiveContent({ objective, accountId, onSaved, onCancel }) {
  const { closeDrawer } = useWorkspaceDrawer();
  const { choices, choicesLoading } = useGetSignalChoices();
  const { standardDepartments } = useGetContactChoices();

  const whatOptions = choices?.signal_whats ?? [];
  const dimensionOptions = choices?.signal_dimensions ?? [];
  const departmentOptions = standardDepartments || [];

  const initialValues = useMemo(
    () => ({
      summary: objective?.summary || "",
      what: objective?.what || "",
      dimension: objective?.dimension || "",
      scope_level: objective?.scope_level || OBJECTIVE_SCOPE.BUSINESS,
      target_department: fkId(objective?.target_department),
      target_contact: fkId(objective?.target_contact),
      success_criteria: objective?.success_criteria || "",
      target_date: objective?.target_date || "",
      notes: objective?.notes || "",
      source_quote: objective?.source_quote || "",
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [objective?.id],
  );

  const formik = useFormik({
    enableReinitialize: true,
    validationSchema,
    initialValues,
    onSubmit: async (values, { setSubmitting }) => {
      const payload = {
        summary: values.summary.trim(),
        what: values.what,
        dimension: values.dimension,
        scope_level: values.scope_level,
        target_department: values.target_department || null,
        target_contact: values.target_contact || null,
        success_criteria: values.success_criteria || "",
        target_date: values.target_date || null,
        notes: values.notes || "",
        source_quote: values.source_quote || "",
      };
      try {
        const result = await updateSignal("objective", objective.id, payload);
        if (!result?.success) {
          displayErrorSnackbar(result);
          return;
        }
        displaySuccessSnackbar("Objective updated");
        // Return to the detail with the updated signal instead of closing. Build
        // a display-friendly merge (re-resolve the axis labels + the department
        // object) so the read drawer renders the new values immediately.
        if (onSaved) {
          const updatedSignal = {
            ...objective,
            summary: payload.summary,
            what: values.what,
            dimension: values.dimension,
            what_display: resolveLabel(whatOptions, values.what) ?? objective?.what_display,
            dimension_display:
              resolveLabel(dimensionOptions, values.dimension) ?? objective?.dimension_display,
            scope_level: values.scope_level,
            target_department: values.target_department
              ? { id: values.target_department, name: resolveLabel(departmentOptions, values.target_department) }
              : null,
            target_contact: values.target_contact ? objective?.target_contact ?? null : null,
            success_criteria: payload.success_criteria,
            target_date: payload.target_date,
            notes: payload.notes,
            source_quote: payload.source_quote,
          };
          onSaved(updatedSignal);
        } else {
          closeDrawer();
        }
      } catch (err) {
        displayErrorSnackbar(err);
      } finally {
        setSubmitting(false);
      }
    },
  });

  const { values, errors, setFieldValue } = formik;
  const set = (name) => (v) => setFieldValue(name, v);

  // Live "Domain × Dimension" recap (reproduced from the original).
  const canonicalPreview = useMemo(() => {
    if (!values.what || !values.dimension) return null;
    return `objective:${values.what}:${values.dimension}`;
  }, [values.what, values.dimension]);

  const axisPreview = useMemo(() => {
    const whatLabel = resolveLabel(whatOptions, values.what);
    const dimensionLabel = resolveLabel(dimensionOptions, values.dimension);
    if (!whatLabel || !dimensionLabel) return null;
    return `${whatLabel} × ${dimensionLabel}`;
  }, [whatOptions, dimensionOptions, values.what, values.dimension]);

  // The scope pill raises a draft patch of scope fields — apply each to the draft.
  const applyScopePatch = (patch) => {
    Object.entries(patch).forEach(([k, v]) => setFieldValue(k, v));
  };

  const isDepartment = values.scope_level === OBJECTIVE_SCOPE.DEPARTMENT;

  return (
    <DrawerContentLayout
      onSave={formik.handleSubmit}
      onCancel={() => (onCancel ? onCancel() : closeDrawer())}
      saveDisabled={!formik.isValid || !formik.dirty || formik.isSubmitting}
    >
      <Stack spacing={2.5}>
        {/* ---- SECTION 1 — What's the goal? ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={1}
            title="What's the goal?"
            subtitle="Describe the objective and pick its canonical axes."
          />

          <InlineEditableValue
            name="summary"
            label="Summary"
            type="textarea"
            value={values.summary}
            onChange={set("summary")}
            placeholder="Required"
            error={Boolean(errors.summary)}
            helperText={errors.summary}
          />
          <InlineEditableValue
            name="what"
            label="Domain"
            type="select"
            options={whatOptions}
            value={values.what}
            onChange={set("what")}
            placeholder="No domain"
            disabled={choicesLoading}
            error={Boolean(errors.what)}
            helperText={errors.what}
          />
          <InlineEditableValue
            name="dimension"
            label="Dimension"
            type="select"
            options={dimensionOptions}
            value={values.dimension}
            onChange={set("dimension")}
            placeholder="No dimension"
            disabled={choicesLoading}
            error={Boolean(errors.dimension)}
            helperText={errors.dimension}
          />

          {/* Live canonical preview */}
          {axisPreview && (
            <Box
              sx={{
                px: 1.5,
                py: 1,
                bgcolor: (theme) => theme.aphoriQ?.surface?.level2,
                borderRadius: 1,
                borderLeftStyle: "solid",
                borderLeftWidth: 3,
                borderLeftColor: "info.main",
              }}
            >
              <Typography variant="caption" color="text.secondary">
                This is a{" "}
                <Box component="span" sx={{ fontWeight: 600, color: "text.primary" }}>
                  {axisPreview}
                </Box>{" "}
                goal
              </Typography>
              <Typography
                variant="caption"
                color="text.disabled"
                display="block"
                sx={{ fontFamily: "monospace", fontSize: "0.7rem", mt: 0.25 }}
              >
                canonical_key: {canonicalPreview}
              </Typography>
            </Box>
          )}
        </Stack>

        <Divider />

        {/* ---- SECTION 2 — Who owns it? (scope → pill + original dept Select) ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={2}
            title="Who owns it?"
            subtitle="Pick the organisational scope driving this goal."
          />

          <ObjectiveScopePill
            value={{ scope_level: values.scope_level }}
            onChange={applyScopePatch}
          />

          {/* DEPARTMENT → target_department: the ORIGINAL MUI Select (mono).
              Wrapped with extra top padding (spacing token) so it's aerated from
              the pills row — padding adds ON TOP of the Stack's own row spacing
              (a child margin would just be overridden by the Stack). */}
          {isDepartment && (
            <Box data-testid="scope-department-field" sx={{ pt: 1 }}>
            <FormControl
              fullWidth
              size="small"
              error={formik.touched.target_department && Boolean(errors.target_department)}
            >
              <InputLabel id="objective-target-dept-label">Target Department *</InputLabel>
              <Select
                labelId="objective-target-dept-label"
                id="objective-target-department"
                name="target_department"
                // Always a defined string: scopePatch(BUSINESS) clears
                // target_department to null, so guard against null/undefined
                // (a null `value` makes MUI's Select uncontrolled → the React
                // "value should not be null / controlled↔uncontrolled" warning).
                value={values.target_department ?? ""}
                onChange={formik.handleChange}
                onBlur={formik.handleBlur}
                label="Target Department *"
              >
                {departmentOptions.map((opt) => (
                  <MenuItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </MenuItem>
                ))}
              </Select>
              {formik.touched.target_department && errors.target_department && (
                <FormHelperText>{errors.target_department}</FormHelperText>
              )}
            </FormControl>
            </Box>
          )}
        </Stack>

        <Divider />

        {/* ---- SECTION 3 — How is success measured? ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={3}
            title="How is success measured?"
            subtitle="Optional — success criteria, deadline, and notes."
          />

          <InlineEditableValue
            name="success_criteria"
            label="Success criteria"
            type="textarea"
            value={values.success_criteria}
            onChange={set("success_criteria")}
            placeholder="No success criteria"
          />
          {/* Target date — double-click reveals the project DatePicker (✓/✗). */}
          <TargetDateField value={values.target_date} onChange={set("target_date")} />
          <InlineEditableValue
            name="notes"
            label="Notes"
            type="textarea"
            value={values.notes}
            onChange={set("notes")}
            placeholder="No notes"
          />
        </Stack>

        <Divider />

        {/* ---- SECTION 4 — Source quote (added) ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={4}
            title="Source quote"
            subtitle="Where does this signal come from"
          />
          <InlineEditableValue
            name="source_quote"
            label="Quote"
            type="textarea"
            value={values.source_quote}
            onChange={set("source_quote")}
            placeholder="No source quote"
          />
        </Stack>
      </Stack>
    </DrawerContentLayout>
  );
}

EditObjectiveContent.propTypes = {
  /** The objective signal to edit (the full detail payload). */
  objective: PropTypes.shape({
    id: PropTypes.string.isRequired,
    summary: PropTypes.string,
    what: PropTypes.string,
    dimension: PropTypes.string,
    scope_level: PropTypes.string,
    target_department: PropTypes.oneOfType([PropTypes.string, PropTypes.object]),
    target_contact: PropTypes.oneOfType([PropTypes.string, PropTypes.object]),
    success_criteria: PropTypes.string,
    target_date: PropTypes.string,
    notes: PropTypes.string,
    source_quote: PropTypes.string,
  }).isRequired,
  /** Account the objective belongs to (reserved for future scoped pickers). */
  accountId: PropTypes.string,
  /** Fired after a successful save with the updated signal — the caller
      revalidates and returns to the detail. Absent → the drawer closes (legacy). */
  onSaved: PropTypes.func,
  /** Fired on Cancel — the caller returns to the detail without saving.
      Absent → the drawer closes (legacy). */
  onCancel: PropTypes.func,
};
