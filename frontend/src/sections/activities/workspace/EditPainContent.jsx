// frontend/src/sections/activities/workspace/EditPainContent.jsx
//
// S3 — the Pain EDIT drawer content, on the standard chassis, a mirror of
// EditObjectiveContent: numbered SectionHeaders + InlineEditableValue
// (read → double-click → inline edit) on DrawerContentLayout (global Save/Cancel).
// The coque owns the "Edit pain" title (passed to openDrawer), so this content
// sets no DrawerContentLayout title. Save PATCHes via updateSignal("pain", id,
// payload); onSaved(updatedSignal) returns to the Pain detail.
//
// The ONE structural difference vs Objective: the department scope is a
// MULTI-department M2M (target_departments), NOT a single FK. Scope model:
//   - two EXCLUSIVE scope pills Company | Department, rendered locally with the
//     shared StatusPill + objectiveScope tokens (ObjectiveScopePill itself is NOT
//     used/modified here — Objective keeps it). scope_level is a single value, so
//     exactly one pill is pressed;
//   - Company  → scope_level BUSINESS, target_departments cleared;
//   - Department → a "+ add department" trigger (same gesture as EditActivityContent's
//     "+ add contact") opens a grouped multi-select whose options EXCLUDE the
//     already-chosen departments; on confirm the chosen departments join a row of
//     real pills (StatusPill), each with a × to remove it.
// Selected departments are stored as {value,label} OBJECTS (the ids are extracted
// only at payload time) to avoid the int(option)/string(id) type mismatch. The
// payload never carries a target_department / target_contact FK.
//
// Theme tokens only. InlineEditableValue supports text / textarea / select.

"use client";

import PropTypes from "prop-types";
import { useMemo, useState } from "react";

import { useFormik } from "formik";
import * as Yup from "yup";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Divider from "@mui/material/Divider";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import PlusOutlined from "@ant-design/icons/PlusOutlined";
import CloseOutlined from "@ant-design/icons/CloseOutlined";

// Project
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import { updateSignal, useGetSignalChoices } from "api/signals/signals";
import { useGetContactChoices } from "api/businessData/contacts";
import { displaySuccessSnackbar, displayErrorSnackbar } from "utils/displayError";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import SectionHeader from "components/display/SectionHeader";
import InlineEditableValue from "components/drawer/InlineEditableValue";
import MultiSelectFilter from "components/filters/MultiSelectFilter";
import StatusPill from "components/chips/StatusPill";
// Reuse the SHARED scope constants + pill colour tokens (objectiveScope is NOT
// modified — ObjectiveScopePill/Objective keep using them unchanged).
import { OBJECTIVE_SCOPE, SCOPE_PILL_OPTIONS, SCOPE_PILL_COLORS } from "utils/objectiveScope";

// ==============================|| HELPERS ||============================== //

function resolveLabel(options, value) {
  if (!value || !options) return null;
  return options.find((o) => o.value === value)?.label ?? value;
}

// Normalise the detail payload's target_departments ([{id,name}] | [id]) to the
// list of {value,label} OBJECTS the form holds (ids kept as strings — str(d.id)).
function toDepartmentObjects(list) {
  if (!Array.isArray(list)) return [];
  return list
    .map((d) =>
      typeof d === "object"
        ? { value: String(d?.id), label: d?.name ?? String(d?.id) }
        : { value: String(d), label: String(d) },
    )
    .filter((d) => d.value && d.value !== "undefined");
}

// ==============================|| VALIDATION ||============================== //
//
// Mirror of Objective for the shared fields. The DEPARTMENTS are deliberately
// NOT validated against the scope: target_departments is an independent M2M
// (never required), so there is NO .when() on scope_level here.

const validationSchema = Yup.object({
  summary: Yup.string()
    .trim()
    .min(10, "Summary must be at least 10 characters")
    .required("Summary is required"),
  what: Yup.string().required("Domain is required"),
  dimension: Yup.string().required("Dimension is required"),
  target_departments: Yup.array().nullable(),
  notes: Yup.string().nullable(),
  related_techstack_mention: Yup.string().nullable(),
  source_quote: Yup.string().nullable(),
});

// ==============================|| EDIT PAIN CONTENT ||============================== //

export default function EditPainContent({ pain, accountId, onSaved, onCancel }) {
  const { closeDrawer } = useWorkspaceDrawer();
  const { choices, choicesLoading } = useGetSignalChoices();
  const { standardDepartments } = useGetContactChoices();

  const whatOptions = choices?.signal_whats ?? [];
  const dimensionOptions = choices?.signal_dimensions ?? [];
  const scopeLevelOptions = choices?.scope_levels ?? [];

  // Options for the department multi-select. The choices endpoint mixes
  // {value,label} and {id,name}, and — crucially — emits the id as an INTEGER
  // (backend contacts choices: {'value': dept.id}) while the signal payload
  // carries department ids as STRINGS (str(d.id)). MultiSelectFilter matches by
  // strict value identity, so BOTH sides must be the same type: stringify the
  // option value (and label) so they line up with the string form ids.
  const departmentOptions = useMemo(
    () =>
      (standardDepartments ?? []).map((d) => ({
        value: String(d.value ?? d.id),
        label: String(d.label ?? d.name),
      })),
    [standardDepartments],
  );

  const initialValues = useMemo(() => {
    const departments = toDepartmentObjects(pain?.target_departments);
    // Explicit scope from the signal; default DEPARTMENT when it already carries
    // departments, else BUSINESS.
    const scope_level =
      pain?.scope_level === OBJECTIVE_SCOPE.DEPARTMENT || departments.length > 0
        ? OBJECTIVE_SCOPE.DEPARTMENT
        : OBJECTIVE_SCOPE.BUSINESS;
    return {
      summary: pain?.summary || "",
      what: pain?.what || "",
      dimension: pain?.dimension || "",
      scope_level,
      // Stored as {value,label} objects (ids extracted only at payload time).
      target_departments: departments,
      notes: pain?.notes || "",
      related_techstack_mention: pain?.related_techstack_mention || "",
      source_quote: pain?.source_quote || "",
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pain?.id]);

  const formik = useFormik({
    enableReinitialize: true,
    validationSchema,
    initialValues,
    onSubmit: async (values, { setSubmitting }) => {
      // Only Pain's writable fields (PainSignalUpdateSerializer). NO FK fields
      // (target_department / target_contact do not exist on Pain).
      //
      // scope_level is EXPLICIT (the chosen pill). Extract the department ids from
      // the stored {value,label} objects; Company (BUSINESS) always sends [] so an
      // edit that switches to company-wide replaces the set on the backend.
      const isDepartment = values.scope_level === OBJECTIVE_SCOPE.DEPARTMENT;
      const departmentIds = isDepartment
        ? (values.target_departments || []).map((d) => d.value)
        : [];
      const payload = {
        summary: values.summary.trim(),
        what: values.what,
        dimension: values.dimension,
        scope_level: values.scope_level,
        target_departments: departmentIds,
        notes: values.notes || "",
        related_techstack_mention: values.related_techstack_mention || "",
        source_quote: values.source_quote || "",
      };
      try {
        const result = await updateSignal("pain", pain.id, payload);
        if (!result?.success) {
          displayErrorSnackbar(result);
          return;
        }
        displaySuccessSnackbar("Pain updated");
        // Return to the detail with the updated signal (display-friendly merge:
        // re-resolve the axis + scope labels + rebuild the departments [{id,name}]
        // list) so the read drawer renders the new values immediately.
        if (onSaved) {
          const updatedSignal = {
            ...pain,
            summary: payload.summary,
            what: values.what,
            dimension: values.dimension,
            what_display: resolveLabel(whatOptions, values.what) ?? pain?.what_display,
            dimension_display:
              resolveLabel(dimensionOptions, values.dimension) ?? pain?.dimension_display,
            scope_level: payload.scope_level,
            scope_level_display:
              resolveLabel(scopeLevelOptions, payload.scope_level) ?? pain?.scope_level_display,
            target_departments: payload.target_departments.map((id) => ({
              id,
              name: resolveLabel(departmentOptions, id),
            })),
            notes: payload.notes,
            related_techstack_mention: payload.related_techstack_mention,
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

  const theme = useTheme();
  const isDepartment = values.scope_level === OBJECTIVE_SCOPE.DEPARTMENT;

  // "+ add department" gesture state: the trigger opens a grouped multi-select
  // whose staged ids are committed as pills on confirm.
  const [adding, setAdding] = useState(false);
  const [staged, setStaged] = useState([]);

  // Exclusive scope choice: scope_level is a single value, so exactly one pill is
  // pressed. Clicking a pill selects it (and clears departments for Company).
  const chooseScope = (key) => {
    if (!key || key === values.scope_level) return;
    setFieldValue("scope_level", key);
    if (key === OBJECTIVE_SCOPE.BUSINESS) {
      // Company-wide → no departments.
      setFieldValue("target_departments", []);
      setStaged([]);
      setAdding(false);
    }
  };

  // The "+ add department" menu never re-proposes an already-chosen department.
  const availableOptions = departmentOptions.filter(
    (o) => !(values.target_departments || []).some((d) => d.value === o.value),
  );

  // Local "+ add" trigger — same gesture/tokens as EditActivityContent's
  // "+ add contact" (text button + PlusOutlined, accent colour).
  const addButton = (onClick, testId, label) => (
    <Button
      variant="text"
      size="small"
      onClick={onClick}
      data-testid={testId}
      startIcon={<PlusOutlined style={{ fontSize: theme.iconSizes.sm }} />}
      sx={{ color: theme.aphoriQ?.accent, px: 0, justifyContent: "flex-start", textTransform: "none" }}
    >
      {label}
    </Button>
  );

  // Commit the staged ids as {value,label} objects (dedup by value), then close.
  const commitStaged = () => {
    const chosen = departmentOptions.filter((o) => staged.includes(o.value));
    const existing = values.target_departments || [];
    const merged = [...existing];
    chosen.forEach((o) => {
      if (!merged.some((d) => d.value === o.value)) {
        merged.push({ value: o.value, label: o.label });
      }
    });
    setFieldValue("target_departments", merged);
    setStaged([]);
    setAdding(false);
  };

  const removeDept = (value) =>
    setFieldValue(
      "target_departments",
      (values.target_departments || []).filter((d) => d.value !== value),
    );

  // Live "Domain × Dimension" recap (guidance, mirror of Objective).
  const canonicalPreview = useMemo(() => {
    if (!values.what || !values.dimension) return null;
    return `pain:${values.what}:${values.dimension}`;
  }, [values.what, values.dimension]);

  const axisPreview = useMemo(() => {
    const whatLabel = resolveLabel(whatOptions, values.what);
    const dimensionLabel = resolveLabel(dimensionOptions, values.dimension);
    if (!whatLabel || !dimensionLabel) return null;
    return `${whatLabel} × ${dimensionLabel}`;
  }, [whatOptions, dimensionOptions, values.what, values.dimension]);

  return (
    <DrawerContentLayout
      onSave={formik.handleSubmit}
      onCancel={() => (onCancel ? onCancel() : closeDrawer())}
      saveDisabled={!formik.isValid || !formik.dirty || formik.isSubmitting}
    >
      <Stack spacing={2.5}>
        {/* ---- SECTION 1 — What's the pain? ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={1}
            title="What's the pain?"
            subtitle="Describe the pain and pick its canonical axes."
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
                bgcolor: "action.hover",
                borderRadius: 1,
              }}
            >
              <Typography variant="caption" color="text.secondary">
                This is a{" "}
                <Box component="span" sx={{ fontWeight: 600, color: "text.primary" }}>
                  {axisPreview}
                </Box>{" "}
                pain
              </Typography>
              <Typography
                variant="caption"
                color="text.disabled"
                display="block"
                sx={{ fontFamily: "monospace", mt: 0.25 }}
              >
                canonical_key: {canonicalPreview}
              </Typography>
            </Box>
          )}
        </Stack>

        <Divider />

        {/* ---- SECTION 2 — Which scope? (explicit Company | Department) ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={2}
            title="Which scope?"
            subtitle="Company-wide, or one or more departments."
          />

          {/* Two EXCLUSIVE scope pills (Company | Department) — same StatusPill as
              the department pills below. scope_level is a single value, so exactly
              one is pressed. Rendered locally (ObjectiveScopePill is untouched and
              still used by Objective); we reuse its shared options + colour tokens. */}
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap data-testid="pain-scope-pills">
            {SCOPE_PILL_OPTIONS.map(({ key, label }) => {
              const isActive = values.scope_level === key;
              const c = isActive ? SCOPE_PILL_COLORS.active : SCOPE_PILL_COLORS.inactive;
              return (
                <StatusPill
                  key={key}
                  data-testid={`scope-pill-${key}`}
                  role="button"
                  tabIndex={0}
                  aria-pressed={isActive}
                  onClick={() => chooseScope(key)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      chooseScope(key);
                    }
                  }}
                  label={label}
                  colorText={c.colorText}
                  colorBg={c.colorBg}
                  sx={{ cursor: "pointer" }}
                />
              );
            })}
          </Stack>

          {/* Department scope → the chosen departments as REAL pills (StatusPill,
              each with a × to remove it) + the "+ add department" gesture. NEVER
              required. */}
          {isDepartment && (
            <Box data-testid="pain-departments-field" sx={{ pt: 1 }}>
              {values.target_departments.length > 0 && (
                <Stack
                  direction="row"
                  spacing={0.5}
                  flexWrap="wrap"
                  useFlexGap
                  // Section-consistent vertical gap (matches the §scope Stack
                  // spacing) between the chosen department pills and the selector.
                  sx={{ mb: 1.5 }}
                  data-testid="pain-department-pills"
                >
                  {values.target_departments.map((d) => (
                    <StatusPill
                      key={d.value}
                      data-testid={`dept-pill-${d.value}`}
                      colorText={SCOPE_PILL_COLORS.active.colorText}
                      colorBg={SCOPE_PILL_COLORS.active.colorBg}
                      label={
                        <Box component="span" sx={{ display: "inline-flex", alignItems: "center", gap: 0.5 }}>
                          {d.label}
                          <Box
                            component="span"
                            role="button"
                            tabIndex={0}
                            aria-label={`Remove ${d.label}`}
                            data-testid={`remove-dept-${d.value}`}
                            onClick={() => removeDept(d.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" || e.key === " ") {
                                e.preventDefault();
                                removeDept(d.value);
                              }
                            }}
                            sx={{ display: "inline-flex", cursor: "pointer" }}
                          >
                            <CloseOutlined style={{ fontSize: theme.iconSizes.xs }} />
                          </Box>
                        </Box>
                      }
                    />
                  ))}
                </Stack>
              )}

              {adding ? (
                <Box data-testid="pain-add-department-picker">
                  {/* Options EXCLUDE already-chosen departments (no duplicates). */}
                  <MultiSelectFilter
                    label="Departments"
                    options={availableOptions}
                    value={staged}
                    onChange={setStaged}
                    placeholder="Select departments…"
                    size="small"
                  />
                  <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                    <Button
                      variant="contained"
                      size="small"
                      onClick={commitStaged}
                      disabled={staged.length === 0}
                      data-testid="confirm-add-departments"
                    >
                      Add
                    </Button>
                    <Button
                      variant="text"
                      size="small"
                      onClick={() => {
                        setStaged([]);
                        setAdding(false);
                      }}
                      data-testid="cancel-add-departments"
                    >
                      Cancel
                    </Button>
                  </Stack>
                </Box>
              ) : (
                addButton(() => setAdding(true), "add-department", "Add department")
              )}
            </Box>
          )}
        </Stack>

        <Divider />

        {/* ---- SECTION 3 — Related tool + Notes (optional) ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={3}
            title="Related tool"
            subtitle="Optional — a tool involved in this pain, and any extra notes."
          />
          <InlineEditableValue
            name="related_techstack_mention"
            label="Related tool"
            type="text"
            value={values.related_techstack_mention}
            onChange={set("related_techstack_mention")}
            placeholder="No related tool"
          />
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

        {/* ---- SECTION 4 — Source quote ---- */}
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

EditPainContent.propTypes = {
  /** The pain signal to edit (the full detail payload). */
  pain: PropTypes.shape({
    id: PropTypes.string.isRequired,
    summary: PropTypes.string,
    what: PropTypes.string,
    dimension: PropTypes.string,
    scope_level: PropTypes.string,
    target_departments: PropTypes.array,
    notes: PropTypes.string,
    related_techstack_mention: PropTypes.string,
    source_quote: PropTypes.string,
  }).isRequired,
  /** Account the pain belongs to (reserved for future scoped pickers). */
  accountId: PropTypes.string,
  /** Fired after a successful save with the updated signal — the caller
      revalidates and returns to the detail. Absent → the drawer closes (legacy). */
  onSaved: PropTypes.func,
  /** Fired on Cancel — the caller returns to the detail without saving.
      Absent → the drawer closes (legacy). */
  onCancel: PropTypes.func,
};
