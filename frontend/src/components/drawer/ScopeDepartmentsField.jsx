// frontend/src/components/drawer/ScopeDepartmentsField.jsx
//
// The "exclusive scope" gesture of the drawer chassis, EXTRACTED from
// EditPainContent (Sprint TechStack T2b, decision D4) so it lives once:
//   - a row of EXCLUSIVE scope pills (StatusPill + the shared objectiveScope
//     colour tokens) — the scope is a single value, exactly one pill pressed;
//   - for the department scope: the chosen departments as REAL pills, each with
//     a × to remove it, plus a "+ add department" trigger opening a grouped
//     multi-select whose options EXCLUDE the already-chosen departments — THE
//     PillsField gesture (components/drawer/PillsField.jsx, TD-303);
//   - any other scope MASKS the departments (they are not cleared, so switching
//     back restores them) — the caller's payload sends [] for those scopes;
//   - `deselectable` (opt-in, default false = Pain behaviour): a click on the
//     ACTIVE pill deselects it — onScopeChange(null), no pill pressed; the
//     caller maps null to its "not said" value (TechStack: UNKNOWN).
// Departments are {value,label} OBJECTS with STRING values (TD-241: the contacts
// choices emit INTEGER ids, signal payloads STRING ids — the caller stringifies
// its options, and toDepartmentObjects normalises the signal payload).
//
// Used by EditTechStackContent (usage scope) and Pain / Impact / Constraint
// (Company | Department scope, lot 3 / 7 — TD-271: their inline copies removed).

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";

// Project
import ClickablePill from "components/chips/ClickablePill";
import PillsField from "components/drawer/PillsField";

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
  deselectable = false,
}) {
  const isDepartment = scope === departmentScope;

  // Exclusive scope choice. A non-department scope MASKS the departments (the
  // pills + "+ add" block only render for the department scope) but does NOT
  // clear them — re-selecting the department scope brings them back untouched.
  const chooseScope = (key) => {
    if (!key) return;
    if (key === scope) {
      // Opt-in: the active pill toggles off (no scope chosen).
      if (!deselectable) return;
      onScopeChange(null);
      return;
    }
    // Leaving the department scope unmounts the (now hidden) "+ add" picker,
    // which collapses it — the departments themselves are kept.
    onScopeChange(key);
  };

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
          return (
            <ClickablePill
              key={key}
              data-testid={`scope-pill-${key}`}
              active={isActive}
              pressed={isActive}
              onClick={() => chooseScope(key)}
              label={label}
            />
          );
        })}
      </Stack>

      {/* Department scope → the chosen departments as REAL pills (each with a ×)
          + the "+ add department" gesture: THE PillsField gesture (TD-303),
          the drawers' test hooks kept through testIds. */}
      {isDepartment && (
        <Box data-testid={`${testIdPrefix}-departments-field`} sx={{ pt: 1 }}>
          <PillsField
            name="department"
            items={departments}
            onChange={onDepartmentsChange}
            options={departmentOptions}
            addLabel="Add department"
            pickerLabel="Departments"
            placeholder="Select departments…"
            error={error}
            testIds={{
              pills: `${testIdPrefix}-department-pills`,
              pill: "dept-pill",
              remove: "remove-dept",
              picker: `${testIdPrefix}-add-department-picker`,
              confirm: "confirm-add-departments",
              cancel: "cancel-add-departments",
            }}
          />
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
  /** Opt-in: a click on the ACTIVE pill deselects it → onScopeChange(null). */
  deselectable: PropTypes.bool,
};
