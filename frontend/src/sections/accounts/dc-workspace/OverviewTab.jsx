// frontend/src/sections/accounts/dc-workspace/OverviewTab.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";

// API
import { useGetManagerNotes } from "api/accounts/decisionCycles";

// Section imports
import ManagerNotesThread from "./ManagerNotesThread";

// ==============================|| OVERVIEW TAB ||============================== //

export default function OverviewTab({ cycleId }) {
  const { notesErrorStatus } = useGetManagerNotes(cycleId);

  // A 403 means the current user may not read this cycle's notes (not the
  // owner, not a manager/admin). Hide the whole block silently — heading
  // included — rather than surfacing an error. Other errors fall through to
  // the thread's own error handling.
  if (notesErrorStatus === 403) {
    return null;
  }

  return (
    <Box>
      <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1.5 }}>
        Coaching Notes
      </Typography>
      <ManagerNotesThread cycleId={cycleId} />
    </Box>
  );
}

OverviewTab.propTypes = {
  cycleId: PropTypes.string.isRequired,
};
