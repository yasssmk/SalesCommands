// frontend/src/sections/accounts/dc-workspace/OverviewTab.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";

// Section imports
import ManagerNotesThread from "./ManagerNotesThread";

// ==============================|| OVERVIEW TAB ||============================== //

export default function OverviewTab({ cycleId }) {
  // ManagerNotesThread owns the 403 decision (it renders null when the current
  // user may not read the notes) AND now owns the "Coaching Notes" title, so
  // there is no orphan header on an empty body and no duplicate 403 guard here.
  return (
    <Box>
      <ManagerNotesThread cycleId={cycleId} />
    </Box>
  );
}

OverviewTab.propTypes = {
  cycleId: PropTypes.string.isRequired,
};
