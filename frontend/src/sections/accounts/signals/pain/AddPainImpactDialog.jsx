// frontend/src/sections/accounts/signals/pain/AddPainImpactDialog.jsx
/**
 * AddPainImpactDialog — dual create/edit dialog for a PainImpact.
 *
 * A PainImpact is the tangible evidence attached to a parent PainSignal:
 *   BUSINESS   — company-wide cost / measurement     → metric + notes
 *   DEPARTMENT — team-level cost / measurement       → department + metric + notes
 *   PERSONAL   — individual human consequence        → contact + human_impact + metric + notes
 *
 * The dialog is organised in two sections:
 *   1. Level picker (3 buttons, required) — drives which form renders below
 *   2. Level-specific form fields
 *
 * Modes:
 *   - CREATE: open with { painSignalId, accountId } — submit hits createPainImpact
 *   - EDIT  : open with { initialImpact, accountId }
 *             painSignalId is read from initialImpact.pain_signal.id
 *             Submit hits updatePainImpact with merged-state validation
 *
 * Error handling (aligned with project convention):
 *   - Field-level errors from the backend → handleFormikError maps them
 *   - Generic / cross-field errors → Alert banner inline at top of form
 *   - Form stays open with user values preserved on failure
 */

"use client";

import PropTypes from "prop-types";
import { useMemo, useState, useEffect, useId } from "react";
import { useFormik } from "formik";
import * as Yup from "yup";

// material-ui
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
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
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";

// ant-design icons
import BankOutlined from "@ant-design/icons/BankOutlined";
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";
import UserOutlined from "@ant-design/icons/UserOutlined";

// project imports
import AsyncContactSelect from "components/AsyncSelection/AsyncContactSelect";
import { useGetContactChoices } from "api/businessData/contacts";
import { createPainImpact, updatePainImpact } from "api/signals/painImpacts";
import { handleFormikError } from "utils/formErrorHandler";

// ==============================|| CONSTANTS ||============================== //

const LEVEL_BUSINESS = "BUSINESS";
const LEVEL_DEPARTMENT = "DEPARTMENT";
const LEVEL_PERSONAL = "PERSONAL";

const LEVEL_OPTIONS = [
  {
    value: LEVEL_BUSINESS,
    label: "Business",
    description: "Company-wide cost or measurement",
    icon: BankOutlined,
  },
  {
    value: LEVEL_DEPARTMENT,
    label: "Department",
    description: "Scoped to a specific team",
    icon: TeamOutlined,
  },
  {
    value: LEVEL_PERSONAL,
    label: "Personal",
    description: "Individual human impact",
    icon: UserOutlined,
  },
];

// ==============================|| VALIDATION ||============================== //

/**
 * Conditional schema mirrors the backend PainImpactCreateSerializer rules:
 *   BUSINESS   → no department, no contact, no human_impact
 *   DEPARTMENT → department required; no contact; no human_impact
 *   PERSONAL   → contact required; no department; human_impact optional
 *
 * We keep client-side validation minimal — the backend remains the source
 * of truth, and backend errors are surfaced via handleFormikError on submit.
 */
const validationSchema = Yup.object({
  level: Yup.string()
    .oneOf([LEVEL_BUSINESS, LEVEL_DEPARTMENT, LEVEL_PERSONAL])
    .required("Level is required"),

  impacted_department: Yup.string()
    .nullable()
    .when("level", {
      is: LEVEL_DEPARTMENT,
      then: (schema) => schema.required("Department is required"),
      otherwise: (schema) => schema.nullable(),
    }),

  impacted_contact: Yup.object()
    .nullable()
    .when("level", {
      is: LEVEL_PERSONAL,
      then: (schema) => schema.required("Impacted contact is required"),
      otherwise: (schema) => schema.nullable(),
    }),

  human_impact: Yup.string().nullable(),
  metric: Yup.string().nullable(),
  notes: Yup.string().nullable(),
});

// ==============================|| INITIAL VALUES ||============================== //

/**
 * Build Formik initial values for CREATE mode — level empty so the user
 * picks it first. All optional fields default to empty-string / null so
 * the form renders controlled inputs from the start.
 */
function buildCreateInitialValues() {
  return {
    level: "",
    impacted_department: "",
    impacted_contact: null,
    human_impact: "",
    metric: "",
    notes: "",
  };
}

/**
 * Build Formik initial values for EDIT mode from an existing impact.
 * Extracts .id from nested department/contact objects for MUI Select compat.
 */
function buildEditInitialValues(impact) {
  return {
    level: impact.level ?? "",
    impacted_department: impact.impacted_department?.id ?? "",
    impacted_contact: impact.impacted_contact ?? null,
    human_impact: impact.human_impact ?? "",
    metric: impact.metric ?? "",
    notes: impact.notes ?? "",
  };
}

// ==============================|| LEVEL OPTION TILE ||============================== //

/**
 * Tile-style toggle button for the level picker — visually richer than a
 * plain Select or ToggleButton, so the rep immediately grasps the 3 modes
 * and picks quickly.
 */
function LevelOptionContent({ option, selected }) {
  const Icon = option.icon;
  return (
    <Stack
      spacing={0.5}
      alignItems="flex-start"
      sx={{ textAlign: "left", width: "100%" }}
    >
      <Stack direction="row" spacing={0.75} alignItems="center">
        <Icon style={{ fontSize: 14 }} />
        <Typography
          variant="body2"
          fontWeight={600}
          color={selected ? "primary.main" : "text.primary"}
        >
          {option.label}
        </Typography>
      </Stack>
      <Typography variant="caption" color="text.secondary">
        {option.description}
      </Typography>
    </Stack>
  );
}

LevelOptionContent.propTypes = {
  option: PropTypes.shape({
    label: PropTypes.string.isRequired,
    description: PropTypes.string.isRequired,
    icon: PropTypes.elementType.isRequired,
  }).isRequired,
  selected: PropTypes.bool.isRequired,
};

// ==============================|| DIALOG ||============================== //

/**
 * AddPainImpactDialog
 *
 * @param {boolean}  open              - Controls dialog visibility
 * @param {Function} onClose           - () => void — called on cancel / close
 * @param {Function} onSuccess         - () => void — called after successful save
 * @param {string}   painSignalId      - UUID of the parent pain. Required in
 *                                       CREATE mode. Ignored in EDIT mode
 *                                       (derived from initialImpact).
 * @param {string}   accountId         - UUID used to scope contact picker.
 *                                       Required when the dialog surfaces
 *                                       a PERSONAL contact field.
 * @param {Object}   initialImpact     - When provided, dialog enters EDIT mode.
 *                                       Must contain { id, pain_signal, level, ... }.
 */
export default function AddPainImpactDialog({
  open,
  onClose,
  onSuccess,
  painSignalId,
  accountId,
  initialImpact,
}) {
  const isEditMode = Boolean(initialImpact);

  /**
   * Stable, instance-unique DOM id for the DialogTitle. React.useId()
   * generates a value that is unique within the React tree and stable
   * across renders, so multiple instances of this dialog can coexist
   * in the DOM (e.g. one mounted by AccountSignalsTab and another by
   * SignalClusterDetailDrawer when both tabs are KeepAlive-mounted)
   * without colliding on the legacy hardcoded `pain-impact-dialog-title`
   * identifier.
   *
   * The `-title` suffix is appended manually because useId() values
   * cannot be reused for multiple elements; if we ever need a separate
   * id for DialogContent (aria-describedby) we'll derive it from the
   * same base with a different suffix.
   */
  const reactId = useId();
  const titleId = `${reactId}-title`;

  // ==============================|| DATA ||============================== //

  const { standardDepartments } = useGetContactChoices();

  const departmentOptions = useMemo(
    () =>
      (standardDepartments ?? []).map((d) => ({
        value: d.value ?? d.id,
        label: d.label ?? d.name,
      })),
    [standardDepartments],
  );

  // Contact picker is scoped to the parent pain's account — prevents
  // cross-account leakage on PERSONAL impacts.
  const contactFilters = useMemo(
    () => ({ account_id: accountId }),
    [accountId],
  );

  // Human impact choices come from the backend via useGetSignalChoices,
  // but that hook lives one level up. To keep this dialog self-contained
  // we hardcode the 5 canonical values here — they are stable enum values
  // defined in backend constants.py (HumanImpact). Labels match backend.
  //
  // If new values are added to HumanImpact, update this list to match.
  const humanImpactOptions = useMemo(
    () => [
      { value: "FRUSTRATION", label: "Frustration" },
      { value: "OVERLOAD", label: "Overload" },
      { value: "STRESS", label: "Stress / Anxiety" },
      { value: "DEMOTIVATION", label: "Demotivation" },
      { value: "CONFLICT", label: "Conflict" },
    ],
    [],
  );

  // ==============================|| GLOBAL FORM ERROR ||============================== //

  /**
   * Top-of-form banner for errors that aren't field-scoped
   * (e.g. "Impacted contact must belong to the same account as the parent pain").
   */
  const [submitError, setSubmitError] = useState(null);

  // ==============================|| FORMIK ||============================== //

  const formik = useFormik({
    initialValues: isEditMode
      ? buildEditInitialValues(initialImpact)
      : buildCreateInitialValues(),
    validationSchema,
    enableReinitialize: true,
    onSubmit: async (values, { setSubmitting }) => {
      setSubmitError(null);

      // Build payload — only include fields meaningful for the selected level.
      // The backend also enforces this, but sending a clean payload keeps
      // the network trace readable and avoids gratuitous 400s.
      const payload = {
        level: values.level,
      };

      if (values.level === LEVEL_DEPARTMENT) {
        payload.impacted_department = values.impacted_department || null;
      } else if (values.level === LEVEL_PERSONAL) {
        payload.impacted_contact = values.impacted_contact?.id ?? null;
        if (values.human_impact) {
          payload.human_impact = values.human_impact;
        }
      }

      if (values.metric?.trim()) payload.metric = values.metric.trim();
      if (values.notes?.trim()) payload.notes = values.notes.trim();

      let result;
      if (isEditMode) {
        // EDIT — PATCH the existing impact.
        // Merged-state validation on the backend expects the caller to send
        // fields consistent with the target level. We send the full merged
        // payload (level + level-specific fields) for safety.
        result = await updatePainImpact(initialImpact.id, payload);
      } else {
        // CREATE — attach to the parent pain.
        result = await createPainImpact({
          ...payload,
          pain_signal: painSignalId,
        });
      }

      setSubmitting(false);

      if (result.success) {
        onSuccess();
        handleClose();
        return;
      }

      // Failure — surface field errors via handleFormikError, and show the
      // global message in the banner. Form stays open with user input.
      handleFormikError(result, formik);
      setSubmitError(
        typeof result.error === "string"
          ? result.error
          : "Failed to save impact",
      );
    },
  });

  // ==============================|| CLOSE / RESET ||============================== //

  const handleClose = () => {
    formik.resetForm();
    setSubmitError(null);
    onClose();
  };

  // Clear banner when user edits a field — acknowledges the error silently
  // and lets the next submit attempt be the source of truth.
  useEffect(() => {
    if (submitError && formik.dirty) {
      setSubmitError(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formik.values]);

  // ==============================|| LEVEL CHANGE ||============================== //

  /**
   * When the user switches level, clear the fields that no longer apply
   * so the payload stays consistent and the backend merged-state validation
   * doesn't reject a PERSONAL impact carrying a stale department, etc.
   */
  const handleLevelChange = (_e, nextLevel) => {
    if (!nextLevel) return;
    formik.setFieldValue("level", nextLevel);

    if (nextLevel !== LEVEL_DEPARTMENT) {
      formik.setFieldValue("impacted_department", "");
    }
    if (nextLevel !== LEVEL_PERSONAL) {
      formik.setFieldValue("impacted_contact", null);
      formik.setFieldValue("human_impact", "");
    }
  };

  // ==============================|| DERIVED ||============================== //

  const currentLevel = formik.values.level;
  const hasLevel = Boolean(currentLevel);

  const title = isEditMode ? "Edit impact" : "Add impact";
  const submitLabel = isEditMode ? "Save changes" : "Add impact";

  // ==============================|| RENDER ||============================== //

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      aria-labelledby={titleId}
    >
      <DialogTitle id={titleId}>
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
        >
          <span>{title}</span>
          <IconButton
            size="small"
            onClick={handleClose}
            disabled={formik.isSubmitting}
            aria-label="Close dialog"
          >
            <CloseOutlined style={{ fontSize: 14 }} />
          </IconButton>
        </Stack>
      </DialogTitle>

      <DialogContent dividers>
        <Stack spacing={2.5}>
          {/* ---- Global error banner ---- */}
          {submitError && (
            <Alert
              severity="error"
              onClose={() => setSubmitError(null)}
              sx={{ fontSize: "0.82rem" }}
            >
              {submitError}
            </Alert>
          )}

          {/* ==================== STEP 1: Level picker ==================== */}
          <Stack spacing={1}>
            <Typography
              variant="caption"
              color="text.secondary"
              fontWeight={600}
            >
              WHAT KIND OF IMPACT?
            </Typography>
            <ToggleButtonGroup
              value={currentLevel}
              exclusive
              onChange={handleLevelChange}
              fullWidth
              sx={{
                "& .MuiToggleButton-root": {
                  textTransform: "none",
                  alignItems: "flex-start",
                  p: 1.25,
                },
              }}
              disabled={isEditMode}
              // In edit mode, level is locked — changing it would require
              // re-validating merged state against the target level, which
              // is easier to enforce by asking the user to delete + recreate.
            >
              {LEVEL_OPTIONS.map((opt) => (
                <ToggleButton
                  key={opt.value}
                  value={opt.value}
                  aria-label={opt.label}
                >
                  <LevelOptionContent
                    option={opt}
                    selected={currentLevel === opt.value}
                  />
                </ToggleButton>
              ))}
            </ToggleButtonGroup>
            {formik.touched.level && formik.errors.level && (
              <FormHelperText error>{formik.errors.level}</FormHelperText>
            )}
            {isEditMode && (
              <Typography variant="caption" color="text.disabled">
                Changing the level of an existing impact is not supported —
                delete this impact and create a new one instead.
              </Typography>
            )}
          </Stack>

          {/* ==================== STEP 2: Level-specific fields ==================== */}
          {hasLevel && (
            <>
              <Divider />
              <Stack spacing={1.5}>
                {/* --- DEPARTMENT-only field --- */}
                {currentLevel === LEVEL_DEPARTMENT && (
                  <FormControl
                    fullWidth
                    size="small"
                    error={
                      formik.touched.impacted_department &&
                      Boolean(formik.errors.impacted_department)
                    }
                  >
                    <InputLabel id="impact-department-label">
                      Department *
                    </InputLabel>
                    <Select
                      labelId="impact-department-label"
                      id="impact-department"
                      name="impacted_department"
                      value={formik.values.impacted_department}
                      onChange={formik.handleChange}
                      onBlur={formik.handleBlur}
                      label="Department *"
                    >
                      {departmentOptions.map((opt) => (
                        <MenuItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </MenuItem>
                      ))}
                    </Select>
                    {formik.touched.impacted_department &&
                      formik.errors.impacted_department && (
                        <FormHelperText>
                          {formik.errors.impacted_department}
                        </FormHelperText>
                      )}
                  </FormControl>
                )}

                {/* --- PERSONAL-only fields --- */}
                {currentLevel === LEVEL_PERSONAL && (
                  <>
                    <AsyncContactSelect
                      label="Impacted Contact *"
                      value={formik.values.impacted_contact}
                      onChange={(_e, contact) =>
                        formik.setFieldValue("impacted_contact", contact)
                      }
                      onBlur={() =>
                        formik.setFieldTouched("impacted_contact", true)
                      }
                      filters={contactFilters}
                      disabled={!accountId}
                      error={
                        formik.touched.impacted_contact &&
                        Boolean(formik.errors.impacted_contact)
                      }
                      helperText={
                        (formik.touched.impacted_contact &&
                          formik.errors.impacted_contact) ||
                        "Who personally experiences this impact."
                      }
                    />

                    <FormControl fullWidth size="small">
                      <InputLabel id="impact-human-label">
                        Human Impact (optional)
                      </InputLabel>
                      <Select
                        labelId="impact-human-label"
                        id="impact-human"
                        name="human_impact"
                        value={formik.values.human_impact}
                        onChange={formik.handleChange}
                        onBlur={formik.handleBlur}
                        label="Human Impact (optional)"
                      >
                        <MenuItem value="">
                          <em>None</em>
                        </MenuItem>
                        {humanImpactOptions.map((opt) => (
                          <MenuItem key={opt.value} value={opt.value}>
                            {opt.label}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </>
                )}

                {/* --- Shared fields for all levels --- */}
                <TextField
                  fullWidth
                  size="small"
                  id="impact-metric"
                  name="metric"
                  label="Metric / Measurement"
                  placeholder="e.g. 120k$/year, 15h/week, 3h/week overtime"
                  value={formik.values.metric}
                  onChange={formik.handleChange}
                  onBlur={formik.handleBlur}
                  error={formik.touched.metric && Boolean(formik.errors.metric)}
                  helperText={
                    (formik.touched.metric && formik.errors.metric) ||
                    "Quantified evidence of the impact. Optional but recommended."
                  }
                />

                <TextField
                  fullWidth
                  size="small"
                  id="impact-notes"
                  name="notes"
                  label="Notes"
                  placeholder="Additional context…"
                  multiline
                  minRows={2}
                  value={formik.values.notes}
                  onChange={formik.handleChange}
                  onBlur={formik.handleBlur}
                  error={formik.touched.notes && Boolean(formik.errors.notes)}
                  helperText={formik.touched.notes && formik.errors.notes}
                />
              </Stack>
            </>
          )}

          {/* When no level picked yet, show a small hint */}
          {!hasLevel && (
            <Box sx={{ py: 1 }}>
              <Typography variant="caption" color="text.disabled">
                Pick a level above to see the form.
              </Typography>
            </Box>
          )}
        </Stack>
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button
          onClick={handleClose}
          color="inherit"
          size="small"
          disabled={formik.isSubmitting}
        >
          Cancel
        </Button>
        <Button
          onClick={formik.handleSubmit}
          variant="contained"
          size="small"
          disabled={formik.isSubmitting || !hasLevel || !formik.isValid}
          startIcon={
            formik.isSubmitting ? (
              <CircularProgress size={12} color="inherit" />
            ) : null
          }
        >
          {submitLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ==============================|| PROP TYPES ||============================== //

AddPainImpactDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onSuccess: PropTypes.func.isRequired,

  /** Required in CREATE mode. Ignored in EDIT mode. */
  painSignalId: PropTypes.string,

  /** Used to scope the contact picker for PERSONAL impacts. */
  accountId: PropTypes.string,

  /** When provided, dialog enters EDIT mode. */
  initialImpact: PropTypes.shape({
    id: PropTypes.string.isRequired,
    level: PropTypes.string,
    metric: PropTypes.string,
    notes: PropTypes.string,
    human_impact: PropTypes.string,
    impacted_department: PropTypes.object,
    impacted_contact: PropTypes.object,
  }),
};
