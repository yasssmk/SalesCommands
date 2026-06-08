// frontend/src/components/display/DrawerFieldRow.jsx

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";

// ==============================|| DRAWER FIELD ROW ||============================== //

export default function DrawerFieldRow({ label, value, children }) {
  const content = children ?? value;
  if (content === null || content === undefined || content === "") return null;

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "flex-start",
        gap: 2,
        py: 0.5,
      }}
    >
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ width: "40%", flexShrink: 0, pt: 0.25 }}
      >
        {label}
      </Typography>
      <Box sx={{ width: "60%" }}>
        {typeof content === "string" ? (
          <Typography variant="body2">{content}</Typography>
        ) : (
          content
        )}
      </Box>
    </Box>
  );
}

DrawerFieldRow.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.node,
  children: PropTypes.node,
};
