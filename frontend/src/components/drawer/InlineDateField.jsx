// frontend/src/components/drawer/InlineDateField.jsx
//
// Inline date field of the drawer chassis — read row that reveals the project
// DatePicker ONLY on a click, with ✓ (keep the draft) / ✗ (restore the pre-edit
// value), same interaction as EditActivityContent's scheduled-date field. The
// form keeps the ISO "YYYY-MM-DD" string; the picker reads/writes a dayjs.
//
// Moved as-is from EditObjectiveContent's TargetDateField (Sprint TechStack
// T2a, decision D1) so Objective and TechStack share ONE date field. The only
// change is that the wording / test ids are derived from `label` and `name`
// instead of being hard-coded to "Target date": with label="Target date" and
// name="target_date" the rendered DOM is identical to the former field.
//   - read row test id ........ inline-read-<name>        (inline-read-target_date)
//   - ✓ / ✗ test ids .......... <name with "-">-confirm / -cancel  (target-date-confirm)
//   - ✓ / ✗ aria-labels ....... "Confirm <label lowercased>" / "Discard <label lowercased>"
//   - empty read text ......... `emptyText` (default "No date set" — Objective)
// Lot 3 / 9b (TD-267): no longer a copy of the click-to-edit mechanics — it
// is InlineEditableValue with a `renderEditor` (the contact pattern,
// EditPeopleContent): read row, one click to open, ✓ = commit, ✗ / Escape =
// cancel (restore), focus leaving the editor keeps the draft. The picker's
// calendar renders inside the editor (popper disablePortal) so a pick never
// reads as "focus left".

"use client";

import PropTypes from "prop-types";

// Project — the shared click-to-edit field + ✓ / ✗ row.
import InlineEditableValue from "components/drawer/InlineEditableValue";
import ConfirmCancelActions from "components/drawer/ConfirmCancelActions";

// MUI
import Stack from "@mui/material/Stack";

// Date picker — the project's standard component (@mui/x-date-pickers + dayjs),
// same as EditActivityContent / OutcomeDrawerContent.
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import dayjs from "dayjs";

const formatDate = (value) => (value ? dayjs(value).format("D MMM YYYY") : null);

export default function InlineDateField({ label, name, value, onChange, emptyText = "No date set" }) {
  const testIdBase = name.replace(/_/g, "-");
  const labelLower = label.toLowerCase();

  return (
    <InlineEditableValue
      name={name}
      label={label}
      value={value}
      // The form keeps "" for an unset date (a cancel restores "" too).
      onChange={(v) => onChange(v ?? "")}
      placeholder={emptyText}
      formatValue={formatDate}
      renderEditor={({ value: draft, onChange: setDraft, commit, cancel }) => (
        <LocalizationProvider dateAdapter={AdapterDayjs}>
          <Stack spacing={1}>
            <DatePicker
              label={label}
              value={draft ? dayjs(draft) : null}
              onChange={(v) => setDraft(v && v.isValid() ? v.format("YYYY-MM-DD") : "")}
              slotProps={{ textField: { fullWidth: true, size: "small" }, popper: { disablePortal: true } }}
            />
            <ConfirmCancelActions
              onConfirm={commit}
              onCancel={cancel}
              testIdBase={testIdBase}
              label={labelLower}
            />
          </Stack>
        </LocalizationProvider>
      )}
    />
  );
}

InlineDateField.propTypes = {
  /** Field label (read caption + picker label), e.g. "Target date". */
  label: PropTypes.string.isRequired,
  /** Form field name, e.g. "target_date" — drives the test ids. */
  name: PropTypes.string.isRequired,
  /** ISO "YYYY-MM-DD" string, or "" / null when unset. */
  value: PropTypes.string,
  onChange: PropTypes.func.isRequired,
  /** Read text when no date is set (default "No date set"). */
  emptyText: PropTypes.string,
};
