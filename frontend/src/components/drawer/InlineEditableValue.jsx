// frontend/src/components/drawer/InlineEditableValue.jsx
//
// SE-b — a SHARED double-click-to-edit field for drawer content. Read by default
// (a muted label + the value, or an italic placeholder when empty). DOUBLE-CLICK
// the value flips it to an inline, aphoriQ-themed input (text / textarea /
// select). Typing raises onChange(newValue) so the PARENT holds the draft — this
// field never PATCHes on its own. Enter (or blur) returns to read keeping the
// value; Escape reverts the in-flight edit to the value captured at edit start.
//
// No hardcoded hex/px — the input is a plain MUI TextField (themed) and the read
// rows use aphoriQ text tokens.

"use client";

import PropTypes from "prop-types";
import { useRef, useState } from "react";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import FormHelperText from "@mui/material/FormHelperText";
import MenuItem from "@mui/material/MenuItem";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

export default function InlineEditableValue({
  name,
  label,
  value,
  onChange,
  type = "text",
  options = [],
  placeholder = "—",
  error = false,
  helperText,
  disabled = false,
}) {
  const aq = useTheme().aphoriQ;
  const [editing, setEditing] = useState(false);
  // The value at the moment editing began — Escape reverts to it.
  const startRef = useRef(value);

  const startEdit = () => {
    if (disabled) return;
    startRef.current = value;
    setEditing(true);
  };
  const commit = () => setEditing(false);
  const cancel = () => {
    onChange(startRef.current);
    setEditing(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && type !== "textarea") {
      e.preventDefault();
      commit();
    } else if (e.key === "Escape") {
      e.preventDefault();
      cancel();
    }
  };

  // ---- Label (shared by both modes) ----
  const labelNode = (
    <Typography variant="caption" sx={{ color: aq.text.muted, display: "block", mb: 0.25 }}>
      {label}
    </Typography>
  );

  // ---- EDIT ----
  if (editing) {
    return (
      <Box>
        {labelNode}
        <TextField
          fullWidth
          size="small"
          autoFocus
          select={type === "select"}
          multiline={type === "textarea"}
          minRows={type === "textarea" ? 3 : undefined}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={commit}
          error={error}
          helperText={error ? helperText : undefined}
          inputProps={{ "data-testid": `inline-input-${name}` }}
        >
          {type === "select" &&
            options.map((o) => (
              <MenuItem key={o.value} value={o.value}>
                {o.label}
              </MenuItem>
            ))}
        </TextField>
      </Box>
    );
  }

  // ---- READ ----
  const isEmpty = value === null || value === undefined || value === "";
  const displayValue =
    type === "select" && !isEmpty
      ? options.find((o) => o.value === value)?.label ?? value
      : value;

  return (
    <Box>
      {labelNode}
      <Box
        data-testid={`inline-read-${name}`}
        onDoubleClick={startEdit}
        sx={{ cursor: disabled ? "default" : "pointer", py: 0.25 }}
      >
        {isEmpty ? (
          <Typography variant="body2" sx={{ color: aq.text.subtle, fontStyle: "italic" }}>
            {placeholder}
          </Typography>
        ) : (
          <Typography variant="body2" color="text.primary" sx={{ whiteSpace: "pre-line" }}>
            {displayValue}
          </Typography>
        )}
      </Box>
      {error && helperText && <FormHelperText error>{helperText}</FormHelperText>}
    </Box>
  );
}

InlineEditableValue.propTypes = {
  /** Stable id used for the read/input test hooks. */
  name: PropTypes.string.isRequired,
  /** Muted caption shown above the value in both modes. */
  label: PropTypes.string.isRequired,
  /** Current (controlled) value — the parent owns the draft. */
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  /** Raised with the new value on every keystroke (a draft; no PATCH here). */
  onChange: PropTypes.func.isRequired,
  /** Input kind: text | textarea | select. */
  type: PropTypes.oneOf(["text", "textarea", "select"]),
  /** Options for type="select": [{ value, label }]. */
  options: PropTypes.arrayOf(PropTypes.shape({ value: PropTypes.any, label: PropTypes.node })),
  /** Muted italic text shown when the value is empty. */
  placeholder: PropTypes.string,
  error: PropTypes.bool,
  helperText: PropTypes.string,
  disabled: PropTypes.bool,
};
