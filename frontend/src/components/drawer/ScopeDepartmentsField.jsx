// frontend/src/components/drawer/ScopeDepartmentsField.jsx
//
// The "exclusive scope" gesture of the drawer chassis, EXTRACTED from
// EditPainContent (Sprint TechStack T2b, decision D4) so it lives once:
//   - a row of EXCLUSIVE scope pills (StatusPill + the shared objectiveScope
//     colour tokens) — the scope is a single value, exactly one pill pressed;
//   - for the department scope: the chosen departments as REAL pills, each with
//     a × to remove it, plus a "+ add department" trigger (same gesture as
//     EditActivityContent's "+ add contact") opening a grouped multi-select whose
//     options EXCLUDE the already-chosen departments; on confirm the staged
//     departments join the pills;
//   - any other scope MASKS the departments (they are not cleared, so switching
//     back restores them) — the caller's payload sends [] for those scopes.
// Departments are {value,label} OBJECTS with STRING values (TD-241: the contacts
// choices emit INTEGER ids, signal payloads STRING ids — the caller stringifies
// its options, and toDepartmentObjects normalises the signal payload).
//
// Used by EditTechStackContent only for now; Pain / Impact / Constraint keep
// their inline copy (migration tracked in TECH_DEBT).

"use client";

import PropTypes from "prop-types";
import { useState } from "react";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import FormHelperText from "@mui/material/FormHelperText";
import Stack from "@mui/material/Stack";

// Icons
import PlusOutlined from "@ant-design/icons/PlusOutlined";
import CloseOutlined from "@ant-design/icons/CloseOutlined";

// Project
import MultiSelectFilter from "components/filters/MultiSelectFilter";
import StatusPill from "components/chips/StatusPill";
import { SCOPE_PILL_COLORS } from "utils/objectiveScope";

// Normalise a signal payload's department list ([{id,name}] | [id]) to the
// list of {value,label} OBJECTS the form holds (ids kept as strings).
export function toDepartmentObjects(list) {
  if (!Array.isArray(list)) return [];
  return list
    .map((d) =>
      typeof d === "object"
        ? { value: String(d?.id), label: d?.name ?? String(d?.id) }
        : { value: String(d), label: String(d) },
    )
    .filter((d) => d.value && d.value !== "undefined");
}

export default function ScopeDepartmentsField({
  scopeOptions,
  scope,
  onScopeChange,
  departmentScope,
  departments,
  onDepartmentsChange,
  departmentOptions,
  testIdPrefix,
  error,
}) {
  const theme = useTheme();
  const isDepartment = scope === departmentScope;

  // "+ add department" gesture state: the trigger opens a grouped multi-select
  // whose staged ids are committed as pills on confirm.
  const [adding, setAdding] = useState(false);
  const [staged, setStaged] = useState([]);

  // Exclusive scope choice. A non-department scope MASKS the departments (the
  // pills + "+ add" block only render for the department scope) but does NOT
  // clear them — re-selecting the department scope brings them back untouched.
  const chooseScope = (key) => {
    if (!key || key === scope) return;
    onScopeChange(key);
    if (key !== departmentScope) {
      // Collapse the (now hidden) "+ add" picker UI — but keep the departments.
      setStaged([]);
      setAdding(false);
    }
  };

  // The "+ add department" menu never re-proposes an already-chosen department.
  const availableOptions = departmentOptions.filter(
    (o) => !(departments || []).some((d) => d.value === o.value),
  );

  // Commit the staged ids as {value,label} objects (dedup by value), then close.
  const commitStaged = () => {
    const chosen = departmentOptions.filter((o) => staged.includes(o.value));
    const merged = [...(departments || [])];
    chosen.forEach((o) => {
      if (!merged.some((d) => d.value === o.value)) {
        merged.push({ value: o.value, label: o.label });
      }
    });
    onDepartmentsChange(merged);
    setStaged([]);
    setAdding(false);
  };

  const removeDept = (value) =>
    onDepartmentsChange((departments || []).filter((d) => d.value !== value));

  return (
    <>
      {/* EXCLUSIVE scope pills — exactly one is pressed. */}
      <Stack
        direction="row"
        spacing={1}
        flexWrap="wrap"
        useFlexGap
        data-testid={`${testIdPrefix}-scope-pills`}
      >
        {scopeOptions.map(({ key, label }) => {
          const isActive = scope === key;
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

      {/* Department scope → the chosen departments as REAL pills (each with a ×)
          + the "+ add department" gesture. */}
      {isDepartment && (
        <Box data-testid={`${testIdPrefix}-departments-field`} sx={{ pt: 1 }}>
          {departments.length > 0 && (
            <Stack
              direction="row"
              spacing={0.5}
              flexWrap="wrap"
              useFlexGap
              sx={{ mb: 1.5 }}
              data-testid={`${testIdPrefix}-department-pills`}
            >
              {departments.map((d) => (
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
            <Box data-testid={`${testIdPrefix}-add-department-picker`}>
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
            // "+ add" trigger — same gesture/tokens as EditActivityContent's
            // "+ add contact" (text button + PlusOutlined, accent colour).
            <Button
              variant="text"
              size="small"
              onClick={() => setAdding(true)}
              data-testid="add-department"
              startIcon={<PlusOutlined style={{ fontSize: theme.iconSizes.sm }} />}
              sx={{ color: theme.aphoriQ?.accent, px: 0, justifyContent: "flex-start", textTransform: "none" }}
            >
              Add department
            </Button>
          )}

          {error && <FormHelperText error>{error}</FormHelperText>}
        </Box>
      )}
    </>
  );
}

ScopeDepartmentsField.propTypes = {
  /** The exclusive scope pills, in display order: [{ key, label }]. */
  scopeOptions: PropTypes.arrayOf(
    PropTypes.shape({ key: PropTypes.string.isRequired, label: PropTypes.node }),
  ).isRequired,
  /** The current scope key (exactly one pill pressed). */
  scope: PropTypes.string,
  onScopeChange: PropTypes.func.isRequired,
  /** The scope key that shows the departments. */
  departmentScope: PropTypes.string.isRequired,
  /** The chosen departments: [{ value (string), label }]. */
  departments: PropTypes.arrayOf(
    PropTypes.shape({ value: PropTypes.string, label: PropTypes.node }),
  ).isRequired,
  onDepartmentsChange: PropTypes.func.isRequired,
  /** All departments: [{ value (STRING), label }] — stringify int ids (TD-241). */
  departmentOptions: PropTypes.arrayOf(
    PropTypes.shape({ value: PropTypes.string, label: PropTypes.node }),
  ).isRequired,
  /** Prefix of the field-level test ids (e.g. "techstack"). */
  testIdPrefix: PropTypes.string.isRequired,
  /** Error message shown under the department scope (e.g. none chosen). */
  error: PropTypes.string,
};
