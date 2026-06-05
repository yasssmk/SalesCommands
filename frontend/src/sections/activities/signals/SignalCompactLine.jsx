// frontend/src/sections/activities/signals/SignalCompactLine.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// Icons
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
} from "@ant-design/icons";

// Project imports
import SignalTypeChip from "components/chips/SignalTypeChip";
import SignalStatusChip from "components/chips/SignalStatusChip";

function truncate(str, max = 80) {
  if (!str) return "—";
  return str.length > max ? `${str.slice(0, max)}…` : str;
}

// ==============================|| SIGNAL COMPACT LINE ||============================== //

export default function SignalCompactLine({
  signal,
  signalType,
  onSelect,
  onValidate,
  onReject,
  isLocked,
}) {
  const isPending = signal.status === "PENDING";
  const isRejected = signal.status === "REJECTED";

  const summaryText =
    signalType === "tech-stack"
      ? signal.tech_catalog_entry?.product_name ||
        signal.tech_catalog_entry?.company_name ||
        "Unknown tool"
      : signal.summary;

  return (
    <Box
      onClick={() => onSelect?.(signal, signalType)}
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 1,
        px: 1.5,
        py: 0.75,
        borderRadius: 1,
        cursor: "pointer",
        opacity: isRejected ? 0.5 : 1,
        "&:hover": {
          bgcolor: "action.hover",
        },
        transition: "background-color 0.15s",
      }}
    >
      <SignalTypeChip signalType={signalType} size="small" />

      <Typography
        variant="body2"
        sx={{
          flex: 1,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {truncate(summaryText)}
      </Typography>

      <SignalStatusChip status={signal.status} size="small" />

      {isPending && !isLocked && (
        <Stack direction="row" spacing={0.25}>
          <Tooltip title="Validate">
            <IconButton
              size="small"
              color="success"
              onClick={(e) => {
                e.stopPropagation();
                onValidate?.(signal, signalType);
              }}
              aria-label="Validate signal"
            >
              <CheckCircleOutlined style={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
          <Tooltip title="Reject">
            <IconButton
              size="small"
              color="error"
              onClick={(e) => {
                e.stopPropagation();
                onReject?.(signal, signalType);
              }}
              aria-label="Reject signal"
            >
              <CloseCircleOutlined style={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
        </Stack>
      )}
    </Box>
  );
}

SignalCompactLine.propTypes = {
  signal: PropTypes.shape({
    id: PropTypes.string.isRequired,
    status: PropTypes.string.isRequired,
    summary: PropTypes.string,
    tech_catalog_entry: PropTypes.shape({
      product_name: PropTypes.string,
      company_name: PropTypes.string,
    }),
  }).isRequired,
  signalType: PropTypes.oneOf(["pain", "objective", "impact", "tech-stack"])
    .isRequired,
  onSelect: PropTypes.func,
  onValidate: PropTypes.func,
  onReject: PropTypes.func,
  isLocked: PropTypes.bool,
};
