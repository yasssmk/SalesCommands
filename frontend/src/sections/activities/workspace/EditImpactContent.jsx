// frontend/src/sections/activities/workspace/EditImpactContent.jsx
//
// S3 — the Impact EDIT drawer content, on the standard chassis, a mirror of
// EditPainContent: numbered SectionHeaders + InlineEditableValue (read →
// double-click → inline edit) on DrawerContentLayout (global Save/Cancel). The
// coque owns the "Edit impact" title (passed to openDrawer), so this content
// sets no DrawerContentLayout title. Save PATCHes via updateSignal("impact",
// id, payload); onSaved(updatedSignal) returns to the Impact detail.
//
// Scope model is IDENTICAL to Pain (Impact scope == Pain scope): two EXCLUSIVE
// scope pills Company | Department (rendered locally with the shared StatusPill +
// objectiveScope tokens; ObjectiveScopePill itself is NOT used/modified here),
// Company → scope_level BUSINESS with departments MASKED (not cleared), Department
// → a "+ add department" grouped multi-select whose options EXCLUDE the already
// chosen, chosen departments as real pills each with a ×. Departments are stored
// as {value,label} OBJECTS (ids extracted only at payload time) to avoid the
// int(option)/string(id) type mismatch. The payload never carries a FK.
//
// Deltas vs Pain: NO notes, NO related_techstack_mention (absent on Impact).
// Adds the Metrics section — impact_type (select, REQUIRED), metric_text
// (textarea, optional), human_impact (select, optional with an empty option).
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
// Mirror of Pain for the shared fields, plus impact_type REQUIRED. metric_text
// and human_impact are optional. The DEPARTMENTS are deliberately NOT validated
// against the scope: target_departments is an independent M2M (never required),
// so there is NO .when() on scope_level here.

const validationSchema = Yup.object({
  summary: Yup.string()
    .trim()
    .min(10, "Summary must be at least 10 characters")
    .required("Summary is required"),
  what: Yup.string().required("Domain is required"),
  dimension: Yup.string().required("Dimension is required"),
  impact_type: Yup.string().required("Impact type is required"),
  metric_text: Yup.string().nullable(),
  human_impact: Yup.string().nullable(),
  target_departments: Yup.array().nullable(),
  source_quote: Yup.string().nullable(),
});

// ==============================|| EDIT IMPACT CONTENT ||============================== //

export default function EditImpactContent({ impact, accountId, onSaved, onCancel }) {
  const { closeDrawer } = useWorkspaceDrawer();
  const { choices, choicesLoading } = useGetSignalChoices();
  const { standardDepartments } = useGetContactChoices();

  const whatOptions = choices?.signal_whats ?? [];
  const dimensionOptions = choices?.signal_dimensions ?? [];
  const scopeLevelOptions = choices?.scope_levels ?? [];
  const impactTypeOptions = choices?.impact_types ?? [];
  // human_impact is optional → prepend an empty option so it can be cleared.
  const humanImpactOptions = useMemo(
    () => [{ value: "", label: "—" }, ...(choices?.human_impacts ?? [])],
    [choices?.human_impacts],
  );

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
    const departments = toDepartmentObjects(impact?.target_departments);
    // Explicit scope from the signal; default DEPARTMENT when it already carries
    // departments, else BUSINESS.
    const scope_level =
      impact?.scope_level === OBJECTIVE_SCOPE.DEPARTMENT || departments.length > 0
        ? OBJECTIVE_SCOPE.DEPARTMENT
        : OBJECTIVE_SCOPE.BUSINESS;
    return {
      summary: impact?.summary || "",
      what: impact?.what || "",
      dimension: impact?.dimension || "",
      scope_level,
      // Stored as {value,label} objects (ids extracted only at payload time).
      target_departments: departments,
      // Metrics — raw values (not *_display).
      impact_type: impact?.impact_type || "",
      metric_text: impact?.metric_text || "",
      human_impact: impact?.human_impact || "",
      source_quote: impact?.source_quote || "",
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [impact?.id]);

  const formik = useFormik({
    enableReinitialize: true,
    validationSchema,
    initialValues,
    onSubmit: async (values, { setSubmitting }) => {
      // Only Impact's writable fields (ImpactSignalUpdateSerializer). NO FK
      // fields (target_department / target_contact do not exist on Impact); NO
      // notes / related_techstack_mention (absent on Impact).
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
        impact_type: values.impact_type,
        metric_text: values.metric_text || "",
        human_impact: values.human_impact || "",
        source_quote: values.source_quote || "",
      };
      try {
        const result = await updateSignal("impact", impact.id, payload);
        if (!result?.success) {
          displayErrorSnackbar(result);
          return;
        }
        displaySuccessSnackbar("Impact updated");
        // Return to the detail with the updated signal (display-friendly merge:
        // re-resolve the axis + scope + metrics labels + rebuild the departments
        // [{id,name}] list) so the read drawer renders the new values immediately.
        if (onSaved) {
          const updatedSignal = {
            ...impact,
            summary: payload.summary,
            what: values.what,
            dimension: values.dimension,
            what_display: resolveLabel(whatOptions, values.what) ?? impact?.what_display,
            dimension_display:
              resolveLabel(dimensionOptions, values.dimension) ?? impact?.dimension_display,
            scope_level: payload.scope_level,
            scope_level_display:
              resolveLabel(scopeLevelOptions, payload.scope_level) ?? impact?.scope_level_display,
            target_departments: payload.target_departments.map((id) => ({
              id,
              name: resolveLabel(departmentOptions, id),
            })),
            impact_type: payload.impact_type,
            impact_type_display:
              resolveLabel(impactTypeOptions, payload.impact_type) ?? impact?.impact_type_display,
            metric_text: payload.metric_text,
            human_impact: payload.human_impact,
            human_impact_display: payload.human_impact
              ? resolveLabel(humanImpactOptions, payload.human_impact)
              : null,
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
  // pressed. Company MASKS the departments (the pills + "+ add" block only render
  // for DEPARTMENT) but does NOT clear them from the form — re-selecting Department
  // brings them back untouched. The × on a pill stays the only way to remove one.
  // The payload derives target_departments from scope_level (Company → []), so the
  // memorised-but-hidden list never leaks into a Company save.
  const chooseScope = (key) => {
    if (!key || key === values.scope_level) return;
    setFieldValue("scope_level", key);
    if (key === OBJECTIVE_SCOPE.BUSINESS) {
      // Collapse the (now hidden) "+ add" picker UI — but keep the departments.
      setStaged([]);
      setAdding(false);
    }
  };

  // The "+ add department" menu never re-proposes an already-chosen department.
  const availableOptions = departmentOptions.filter(
    (o) => !(values.target_departments || []).some((d) => d.value === o.value),
  );

  // Local "+ add" trigger — same gesture/tokens as EditPainContent's
  // "+ add department" (text button + PlusOutlined, accent colour).
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

  // Live "Domain × Dimension" recap (guidance, mirror of Pain).
  const canonicalPreview = useMemo(() => {
    if (!values.what || !values.dimension) return null;
    return `impact:${values.what}:${values.dimension}`;
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
        {/* ---- SECTION 1 — What's the impact? ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={1}
            title="What's the impact?"
            subtitle="Describe the impact and pick its canonical axes."
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
                impact
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
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap data-testid="impact-scope-pills">
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
            <Box data-testid="impact-departments-field" sx={{ pt: 1 }}>
              {values.target_departments.length > 0 && (
                <Stack
                  direction="row"
                  spacing={0.5}
                  flexWrap="wrap"
                  useFlexGap
                  // Section-consistent vertical gap (matches the §scope Stack
                  // spacing) between the chosen department pills and the selector.
                  sx={{ mb: 1.5 }}
                  data-testid="impact-department-pills"
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
                <Box data-testid="impact-add-department-picker">
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

        {/* ---- SECTION 3 — Metrics ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={3}
            title="Metrics"
            subtitle="The nature of the impact, its metric, and any human dimension."
          />
          <InlineEditableValue
            name="impact_type"
            label="Impact type"
            type="select"
            options={impactTypeOptions}
            value={values.impact_type}
            onChange={set("impact_type")}
            placeholder="Required"
            disabled={choicesLoading}
            error={Boolean(errors.impact_type)}
            helperText={errors.impact_type}
          />
          <InlineEditableValue
            name="metric_text"
            label="Metric"
            type="textarea"
            value={values.metric_text}
            onChange={set("metric_text")}
            placeholder="No metric"
          />
          <InlineEditableValue
            name="human_impact"
            label="Human impact"
            type="select"
            options={humanImpactOptions}
            value={values.human_impact}
            onChange={set("human_impact")}
            placeholder="No human impact"
            disabled={choicesLoading}
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

EditImpactContent.propTypes = {
  /** The impact signal to edit (the full detail payload). */
  impact: PropTypes.shape({
    id: PropTypes.string.isRequired,
    summary: PropTypes.string,
    what: PropTypes.string,
    dimension: PropTypes.string,
    scope_level: PropTypes.string,
    target_departments: PropTypes.array,
    impact_type: PropTypes.string,
    metric_text: PropTypes.string,
    human_impact: PropTypes.string,
    source_quote: PropTypes.string,
  }).isRequired,
  /** Account the impact belongs to (reserved for future scoped pickers). */
  accountId: PropTypes.string,
  /** Fired after a successful save with the updated signal — the caller
      revalidates and returns to the detail. Absent → the drawer closes (legacy). */
  onSaved: PropTypes.func,
  /** Fired on Cancel — the caller returns to the detail without saving.
      Absent → the drawer closes (legacy). */
  onCancel: PropTypes.func,
};
