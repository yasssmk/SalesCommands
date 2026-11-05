// frontend/src/components/filters/InlinePillsFilter.jsx
//
// Sprint « Cycle de vie des contacts », 8h — THE inline filter: a row of the
// shared ClickablePill (active + pressed, the scope pills' single-choice
// pattern of ScopeDepartmentsField) driven by a filter DEFINITION
// (utils/filters/filterDefinitions — { key, param, label, multiple,
// emptyMeans, options }). Controlled: `value` (string[]) / `onChange`.
//   - multiple: a click adds the value, a click on a chosen one removes it;
//   - single:   a click replaces the value; a click on the active one empties;
//   - empty:    no pill pressed — its meaning (all / the surface) is the
//               definition's emptyMeans, applied by toQueryParams.
// No apply step: the caller applies each change (the drawer panels keep
// their pending → Apply flow on the same definitions).

"use client";

import PropTypes from "prop-types";

// MUI
import Stack from "@mui/material/Stack";

// Project
import ClickablePill from "components/chips/ClickablePill";

export default function InlinePillsFilter({ definition, value = [], onChange, disabled = false }) {
  const toggle = (v) => {
    const chosen = value.includes(v);
    if (definition.multiple) onChange(chosen ? value.filter((x) => x !== v) : [...value, v]);
    else onChange(chosen ? [] : [v]);
  };

  return (
    <Stack
      direction="row"
      spacing={1}
      flexWrap="wrap"
      useFlexGap
      role="group"
      aria-label={definition.label}
      data-testid={`inline-filter-${definition.key}`}
    >
      {definition.options.map((o) => {
        const isActive = value.includes(o.value);
        return (
          <ClickablePill
            key={o.value}
            data-testid={`filter-pill-${definition.key}-${o.value}`}
            label={o.label}
            active={isActive}
            pressed={isActive}
            disabled={disabled}
            onClick={() => toggle(o.value)}
          />
        );
      })}
    </Stack>
  );
}

InlinePillsFilter.propTypes = {
  /** The filter definition (utils/filters/filterDefinitions). */
  definition: PropTypes.shape({
    key: PropTypes.string.isRequired,
    label: PropTypes.string.isRequired,
    multiple: PropTypes.bool,
    options: PropTypes.arrayOf(
      PropTypes.shape({ value: PropTypes.string.isRequired, label: PropTypes.node.isRequired }),
    ).isRequired,
  }).isRequired,
  /** The chosen values ([] = none — see the definition's emptyMeans). */
  value: PropTypes.arrayOf(PropTypes.string),
  /** (values: string[]) => void */
  onChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
};
