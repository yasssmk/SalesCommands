// frontend/src/sections/accounts/dc-workspace/OverviewTab.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";

// Section imports
import ManagerNotesThread from "./ManagerNotesThread";

// ==============================|| OVERVIEW TAB ||============================== //

export default function OverviewTab({ cycleId }) {
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
