// frontend/src/components/drawer/ConfirmCancelActions.jsx
//
// The ✓ (keep the draft) / ✗ (discard it) button row of an inline field in
// edit mode — EXTRACTED from InlineDateField (Sprint TechStack T2d) so the date
// field and the TechStack start-year editor share ONE row (same buttons, style,
// alignment, behaviour) instead of a copy each. Same DOM as before:
//   - right-aligned row, small IconButtons, success ✓ / error ✗ tokens;
//   - test ids  <testIdBase>-confirm / <testIdBase>-cancel;
//   - aria      "Confirm <label>" / "Discard <label>".
// EditActivityContent's DateGroup still carries its own copy (TD-267).

"use client";

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";

// Icons
import CheckOutlined from "@ant-design/icons/CheckOutlined";
import CloseOutlined from "@ant-design/icons/CloseOutlined";

export default function ConfirmCancelActions({ onConfirm, onCancel, testIdBase, label }) {
  const theme = useTheme();
  return (
    <Stack direction="row" justifyContent="flex-end" spacing={0.5}>
      <IconButton
        size="small"
        onClick={onConfirm}
        data-testid={`${testIdBase}-confirm`}
        aria-label={`Confirm ${label}`}
        sx={{ color: "success.main" }}
      >
        <CheckOutlined style={{ fontSize: theme.iconSizes.sm }} />
      </IconButton>
      <IconButton
        size="small"
        onClick={onCancel}
        data-testid={`${testIdBase}-cancel`}
        aria-label={`Discard ${label}`}
        sx={{ color: "error.main" }}
      >
        <CloseOutlined style={{ fontSize: theme.iconSizes.sm }} />
      </IconButton>
    </Stack>
  );
}

ConfirmCancelActions.propTypes = {
  /** ✓ — keep the draft and return to read. */
  onConfirm: PropTypes.func.isRequired,
  /** ✗ — restore the pre-edit value and return to read. */
  onCancel: PropTypes.func.isRequired,
  /** Test-id base, e.g. "target-date" → target-date-confirm / -cancel. */
  testIdBase: PropTypes.string.isRequired,
  /** Lower-cased field label used in the aria-labels, e.g. "target date". */
  label: PropTypes.string.isRequired,
};
