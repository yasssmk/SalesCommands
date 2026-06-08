// frontend/src/sections/activities/signals/SignalsViewToggle.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";

// Icons
import { UnorderedListOutlined, AppstoreOutlined } from "@ant-design/icons";

const STORAGE_PREFIX = "signals_view_";

/**
 * Read persisted view from sessionStorage for a given activity.
 *
 * @param {string} activityId
 * @returns {'grouped'|'flat'}
 */
export function getPersistedView(activityId) {
  if (!activityId) return "grouped";
  try {
    const stored = sessionStorage.getItem(`${STORAGE_PREFIX}${activityId}`);
    return stored === "flat" ? "flat" : "grouped";
  } catch {
    return "grouped";
  }
}

/**
 * Persist view choice to sessionStorage.
 *
 * @param {string} activityId
 * @param {'grouped'|'flat'} view
 */
function persistView(activityId, view) {
  if (!activityId) return;
  try {
    sessionStorage.setItem(`${STORAGE_PREFIX}${activityId}`, view);
  } catch {
    // sessionStorage unavailable — silent fail
  }
}

// ==============================|| SIGNALS VIEW TOGGLE ||============================== //

export default function SignalsViewToggle({ view, onChange, activityId }) {
  const handleChange = (_, newView) => {
    if (!newView) return;
    persistView(activityId, newView);
    onChange(newView);
  };

  return (
    <ToggleButtonGroup
      value={view}
      exclusive
      onChange={handleChange}
      size="small"
      aria-label="Signal view toggle"
    >
      <ToggleButton value="grouped" aria-label="Grouped view">
        <AppstoreOutlined style={{ fontSize: 14, marginRight: 4 }} />
        Grouped
      </ToggleButton>
      <ToggleButton value="flat" aria-label="Flat view">
        <UnorderedListOutlined style={{ fontSize: 14, marginRight: 4 }} />
        Flat
      </ToggleButton>
    </ToggleButtonGroup>
  );
}

SignalsViewToggle.propTypes = {
  view: PropTypes.oneOf(["grouped", "flat"]).isRequired,
  onChange: PropTypes.func.isRequired,
  activityId: PropTypes.string,
};
