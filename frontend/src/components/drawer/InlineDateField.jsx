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
// Still a copy of the InlineEditableValue mechanics (TD-267) — moving it to
// renderEditor is tracked there.

"use client";

import PropTypes from "prop-types";
import { useState, useRef } from "react";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import CheckOutlined from "@ant-design/icons/CheckOutlined";
import CloseOutlined from "@ant-design/icons/CloseOutlined";

// Date picker — the project's standard component (@mui/x-date-pickers + dayjs),
// same as EditActivityContent / OutcomeDrawerContent.
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import dayjs from "dayjs";

export default function InlineDateField({ label, name, value, onChange }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  const [editing, setEditing] = useState(false);
  const startRef = useRef(null);

  const testIdBase = name.replace(/_/g, "-");
  const labelLower = label.toLowerCase();

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
            label={label}
            value={value ? dayjs(value) : null}
            onChange={(v) => onChange(v && v.isValid() ? v.format("YYYY-MM-DD") : "")}
            slotProps={{ textField: { fullWidth: true, size: "small" } }}
          />
          <Stack direction="row" justifyContent="flex-end" spacing={0.5}>
            <IconButton
              size="small"
              onClick={confirm}
              data-testid={`${testIdBase}-confirm`}
              aria-label={`Confirm ${labelLower}`}
              sx={{ color: "success.main" }}
            >
              <CheckOutlined style={{ fontSize: theme.iconSizes.sm }} />
            </IconButton>
            <IconButton
              size="small"
              onClick={cancel}
              data-testid={`${testIdBase}-cancel`}
              aria-label={`Discard ${labelLower}`}
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
        {label}
      </Typography>
      <Box
        data-testid={`inline-read-${name}`}
        onClick={startEdit}
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

InlineDateField.propTypes = {
  /** Field label (read caption + picker label), e.g. "Target date". */
  label: PropTypes.string.isRequired,
  /** Form field name, e.g. "target_date" — drives the test ids. */
  name: PropTypes.string.isRequired,
  /** ISO "YYYY-MM-DD" string, or "" / null when unset. */
  value: PropTypes.string,
  onChange: PropTypes.func.isRequired,
};
