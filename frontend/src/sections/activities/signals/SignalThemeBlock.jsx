// frontend/src/sections/activities/signals/SignalThemeBlock.jsx

"use client";

import PropTypes from "prop-types";
import { useState } from "react";

// MUI
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Collapse from "@mui/material/Collapse";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import { DownOutlined, UpOutlined } from "@ant-design/icons";

// Project imports
import SignalCompactLine from "./SignalCompactLine";

// ==============================|| SIGNAL THEME BLOCK ||============================== //

export default function SignalThemeBlock({
  themeKey,
  themeLabel,
  signals,
  onSelect,
  onValidate,
  onReject,
  isLocked,
  defaultExpanded = true,
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <Box
      sx={{
        border: 1,
        borderColor: "divider",
        borderRadius: 1.5,
        overflow: "hidden",
        mb: 1.5,
      }}
    >
      {/* Header */}
      <Box
        onClick={() => setExpanded((prev) => !prev)}
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          px: 2,
          py: 1,
          bgcolor: "grey.50",
          cursor: "pointer",
          "&:hover": { bgcolor: "grey.100" },
          transition: "background-color 0.15s",
        }}
      >
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="subtitle2" fontWeight={600}>
            {themeLabel}
          </Typography>
          <Chip label={signals.length} size="small" variant="outlined" />
        </Stack>
        <IconButton size="small" aria-label={expanded ? "Collapse" : "Expand"}>
          {expanded ? (
            <UpOutlined style={{ fontSize: 12 }} />
          ) : (
            <DownOutlined style={{ fontSize: 12 }} />
          )}
        </IconButton>
      </Box>

      {/* Signal lines */}
      <Collapse in={expanded}>
        <Divider />
        <Box sx={{ py: 0.5 }}>
          {signals.map((item) => (
            <SignalCompactLine
              key={item.id}
              signal={item}
              signalType={item._signalType}
              onSelect={onSelect}
              onValidate={onValidate}
              onReject={onReject}
              isLocked={isLocked}
            />
          ))}
        </Box>
      </Collapse>
    </Box>
  );
}

SignalThemeBlock.propTypes = {
  themeKey: PropTypes.string.isRequired,
  themeLabel: PropTypes.string.isRequired,
  signals: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      _signalType: PropTypes.string.isRequired,
    }),
  ).isRequired,
  onSelect: PropTypes.func,
  onValidate: PropTypes.func,
  onReject: PropTypes.func,
  isLocked: PropTypes.bool,
  defaultExpanded: PropTypes.bool,
};
