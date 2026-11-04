// frontend/src/components/drawer/PillsField.jsx
//
// A list of values as REAL pills (each with a × to remove it) plus a "+ add"
// trigger — the department gesture of ScopeDepartmentsField, WITHOUT the scope
// pills (Sprint Next steps 5.5). Two ways to add, same gesture:
//   - `options` given → the trigger opens a MultiSelectFilter whose options
//     EXCLUDE the already-chosen values; "Add" commits the staged ones;
//   - no `options` (free text) → the trigger opens a small text input; "Add"
//     (or Enter) commits the typed value, trimmed, never a duplicate.
// Items are {value,label} objects with STRING values; the parent owns them.
// Same tokens as the department pills (StatusPill + SCOPE_PILL_COLORS.active,
// accent "+ add" text button). Test hooks: add-{name}, confirm-add-{name},
// input-add-{name}, remove-{name}-{value}.
// Lot 3 / 6 (TD-303) — THE gesture of ScopeDepartmentsField's departments too,
// through optional props only: `label` absent → no caption (the picker then
// reads `pickerLabel`), `placeholder` for the picker, an `error` line, and
// `testIds` overriding the hooks so a caller keeps its own (pill / remove are
// prefixes completed by "-{value}").

"use client";

import PropTypes from "prop-types";
import { useState } from "react";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import FormHelperText from "@mui/material/FormHelperText";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

// Icons
import PlusOutlined from "@ant-design/icons/PlusOutlined";
import CloseOutlined from "@ant-design/icons/CloseOutlined";

// Project
import MultiSelectFilter from "components/filters/MultiSelectFilter";
import StatusPill from "components/chips/StatusPill";
import { SCOPE_PILL_COLORS } from "utils/objectiveScope";

export default function PillsField({
  name,
  label,
  items,
  onChange,
  options,
  addLabel,
  emptyText,
  pickerLabel,
  placeholder,
  error,
  testIds = {},
}) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  const isPicker = Array.isArray(options);
  const ids = {
    pills: undefined,
    pill: undefined,
    remove: `remove-${name}`,
    picker: undefined,
    confirm: `confirm-add-${name}`,
    cancel: `cancel-add-${name}`,
    ...testIds,
  };

  const [adding, setAdding] = useState(false);
  const [staged, setStaged] = useState([]);
  const [text, setText] = useState("");

  const close = () => {
    setStaged([]);
    setText("");
    setAdding(false);
  };

  // The picker never re-proposes an already-chosen value.
  const availableOptions = isPicker
    ? options.filter((o) => !items.some((i) => i.value === o.value))
    : [];

  const commit = () => {
    const merged = [...items];
    if (isPicker) {
      options
        .filter((o) => staged.includes(o.value))
        .forEach((o) => {
          if (!merged.some((i) => i.value === o.value)) merged.push({ value: o.value, label: o.label });
        });
    } else {
      const value = text.trim();
      if (value && !merged.some((i) => i.value === value)) merged.push({ value, label: value });
    }
    onChange(merged);
    close();
  };

  const remove = (value) => onChange(items.filter((i) => i.value !== value));

  return (
    <Box data-testid={`pills-field-${name}`}>
      {label && (
        <Typography variant="caption" sx={{ color: aq.text.muted, display: "block", mb: 0.5 }}>
          {label}
        </Typography>
      )}

      {items.length > 0 ? (
        <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mb: 1 }} data-testid={ids.pills}>
          {items.map((i) => (
            <StatusPill
              key={i.value}
              {...(ids.pill ? { "data-testid": `${ids.pill}-${i.value}` } : {})}
              colorText={SCOPE_PILL_COLORS.active.colorText}
              colorBg={SCOPE_PILL_COLORS.active.colorBg}
              label={
                <Box component="span" sx={{ display: "inline-flex", alignItems: "center", gap: 0.5 }}>
                  {i.label}
                  <Box
                    component="span"
                    role="button"
                    tabIndex={0}
                    aria-label={`Remove ${i.label}`}
                    data-testid={`${ids.remove}-${i.value}`}
                    onClick={() => remove(i.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        remove(i.value);
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
      ) : (
        emptyText && (
          <Typography variant="body2" sx={{ color: aq.text.subtle, fontStyle: "italic", mb: 0.5 }}>
            {emptyText}
          </Typography>
        )
      )}

      {adding ? (
        <Box data-testid={ids.picker}>
          {isPicker ? (
            <MultiSelectFilter
              label={pickerLabel ?? label}
              options={availableOptions}
              value={staged}
              onChange={setStaged}
              placeholder={placeholder}
              size="small"
            />
          ) : (
            <TextField
              size="small"
              fullWidth
              autoFocus
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  commit();
                }
              }}
              inputProps={{ "data-testid": `input-add-${name}` }}
            />
          )}
          <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
            <Button
              variant="contained"
              size="small"
              onClick={commit}
              disabled={isPicker ? staged.length === 0 : !text.trim()}
              data-testid={ids.confirm}
            >
              Add
            </Button>
            <Button variant="text" size="small" onClick={close} data-testid={ids.cancel}>
              Cancel
            </Button>
          </Stack>
        </Box>
      ) : (
        <Button
          variant="text"
          size="small"
          onClick={() => setAdding(true)}
          data-testid={`add-${name}`}
          startIcon={<PlusOutlined style={{ fontSize: theme.iconSizes.sm }} />}
          sx={{ color: aq.accent, px: 0, justifyContent: "flex-start", textTransform: "none" }}
        >
          {addLabel}
        </Button>
      )}

      {error && <FormHelperText error>{error}</FormHelperText>}
    </Box>
  );
}

PillsField.propTypes = {
  /** Stable id driving the test hooks. */
  name: PropTypes.string.isRequired,
  /** Muted caption above the pills. Absent → no caption. */
  label: PropTypes.string,
  /** The chosen values, as pills: [{ value, label }] (string values). */
  items: PropTypes.arrayOf(
    PropTypes.shape({ value: PropTypes.string.isRequired, label: PropTypes.node }),
  ).isRequired,
  /** (items) => void — the parent owns the list. */
  onChange: PropTypes.func.isRequired,
  /** Picker mode: the values that can be added. Absent → free text. */
  options: PropTypes.arrayOf(
    PropTypes.shape({ value: PropTypes.string.isRequired, label: PropTypes.string.isRequired }),
  ),
  /** Label of the "+ add" trigger. */
  addLabel: PropTypes.string.isRequired,
  /** Muted italic text when there is no pill. */
  emptyText: PropTypes.string,
  /** Picker label (defaults to `label`). */
  pickerLabel: PropTypes.string,
  /** Picker placeholder. */
  placeholder: PropTypes.string,
  /** Error line under the field. */
  error: PropTypes.node,
  /** Test-hook overrides: { pills, pill, remove, picker, confirm, cancel }
      (pill / remove: prefixes completed by "-{value}"). */
  testIds: PropTypes.shape({
    pills: PropTypes.string,
    pill: PropTypes.string,
    remove: PropTypes.string,
    picker: PropTypes.string,
    confirm: PropTypes.string,
    cancel: PropTypes.string,
  }),
};
