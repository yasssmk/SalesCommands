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

"use client";

import PropTypes from "prop-types";
import { useState } from "react";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
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
}) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  const isPicker = Array.isArray(options);

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
      <Typography variant="caption" sx={{ color: aq.text.muted, display: "block", mb: 0.5 }}>
        {label}
      </Typography>

      {items.length > 0 ? (
        <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mb: 1 }}>
          {items.map((i) => (
            <StatusPill
              key={i.value}
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
                    data-testid={`remove-${name}-${i.value}`}
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
        <Box>
          {isPicker ? (
            <MultiSelectFilter
              label={label}
              options={availableOptions}
              value={staged}
              onChange={setStaged}
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
              data-testid={`confirm-add-${name}`}
            >
              Add
            </Button>
            <Button variant="text" size="small" onClick={close} data-testid={`cancel-add-${name}`}>
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
    </Box>
  );
}

PillsField.propTypes = {
  /** Stable id driving the test hooks. */
  name: PropTypes.string.isRequired,
  /** Muted caption above the pills. */
  label: PropTypes.string.isRequired,
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
};
