// frontend/src/components/display/DrawerSection.jsx

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";

// ==============================|| DRAWER SECTION ||============================== //

export default function DrawerSection({ title, children }) {
  if (!children) return null;

  return (
    <Box sx={{ mb: 2.5 }}>
      <Typography
        variant="overline"
        color="text.secondary"
        sx={{ letterSpacing: 1.5, display: "block", mb: 1 }}
      >
        {title}
      </Typography>
      {children}
    </Box>
  );
}

DrawerSection.propTypes = {
  title: PropTypes.string.isRequired,
  children: PropTypes.node,
};
