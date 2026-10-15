// frontend/src/components/drawer/InlineEditableValue.jsx
//
// SE-b — a SHARED click-to-edit field for drawer content. Read by default
// (a muted label + the value, or an italic placeholder when empty). A single
// CLICK on the value flips it to an inline, aphoriQ-themed input (text / textarea /
// select). Typing raises onChange(newValue) so the PARENT holds the draft — this
// field never PATCHes on its own. Enter (or blur) returns to read keeping the
// value; Escape reverts the in-flight edit to the value captured at edit start.
// type="select" opens WITH its menu already open; picking an option raises
// onChange then returns to read; closing the menu without a choice (click
// outside, Escape) returns to read with the value untouched.
// renderEditor({ value, onChange, commit, cancel }) swaps the TextField for a
// custom editor (e.g. a contact picker) under the SAME mechanics: one click to
// open, Escape anywhere inside cancels (captured before the editor's own
// handler, so ONE Escape is enough), focus leaving the editor commits;
// formatValue(value) renders a non-scalar value in read mode.
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
  inputPlaceholder,
  error = false,
  helperText,
  disabled = false,
  renderEditor,
  formatValue,
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

  // ---- EDIT (custom editor) ----
  if (editing && renderEditor) {
    return (
      <Box
        // Capture phase: runs BEFORE the editor's own Escape handling (an open
        // Autocomplete stops the event), so a single Escape cancels.
        onKeyDownCapture={(e) => {
          if (e.key === "Escape") {
            e.preventDefault();
            cancel();
          }
        }}
        // Focus leaving the editor (click outside) commits the draft.
        onBlur={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget)) commit();
        }}
      >
        {labelNode}
        {renderEditor({ value, onChange, commit, cancel })}
      </Box>
    );
  }

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
          // Opt-in: only callers that pass inputPlaceholder get one on the open
          // input; otherwise undefined (no placeholder, the historical behaviour).
          placeholder={inputPlaceholder}
          inputProps={{ "data-testid": `inline-input-${name}` }}
          // MUI fires onChange BEFORE onClose on an option click, so closing
          // the menu always means "done": the choice (if any) is already in
          // the parent's draft, and no choice leaves the value untouched.
          SelectProps={type === "select" ? { defaultOpen: true, onClose: commit } : undefined}
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
  const formatted = formatValue && value != null ? formatValue(value) : undefined;
  const isEmpty =
    value === null || value === undefined || value === "" ||
    (formatValue !== undefined && !formatted);
  const displayValue = formatValue
    ? formatted
    : type === "select" && !isEmpty
      ? options.find((o) => o.value === value)?.label ?? value
      : value;

  return (
    <Box>
      {labelNode}
      <Box
        data-testid={`inline-read-${name}`}
        onClick={startEdit}
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
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number, PropTypes.object]),
  /** Raised with the new value on every keystroke (a draft; no PATCH here). */
  onChange: PropTypes.func.isRequired,
  /** Input kind: text | textarea | select. */
  type: PropTypes.oneOf(["text", "textarea", "select"]),
  /** Options for type="select": [{ value, label }]. */
  options: PropTypes.arrayOf(PropTypes.shape({ value: PropTypes.any, label: PropTypes.node })),
  /** Muted italic text shown when the value is empty. */
  placeholder: PropTypes.string,
  /** Optional placeholder of the OPEN input (edit mode only). Absent → none. */
  inputPlaceholder: PropTypes.string,
  error: PropTypes.bool,
  helperText: PropTypes.string,
  disabled: PropTypes.bool,
  /** Custom editor ({ value, onChange, commit, cancel }) → node, in place of the TextField. */
  renderEditor: PropTypes.func,
  /** Read-mode formatter for a non-scalar value (falsy result → placeholder). */
  formatValue: PropTypes.func,
};
