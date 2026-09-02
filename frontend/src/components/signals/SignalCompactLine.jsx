// frontend/src/components/signals/SignalCompactLine.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// Icons
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  WarningOutlined,
} from "@ant-design/icons";

// Project imports
import SignalTypeChip from "components/chips/SignalTypeChip";
import SignalStatusChip from "components/chips/SignalStatusChip";
import { getTechSummary, getContact, formatContact } from "sections/activities/signals/utils/signalDisplay";

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

  const techInfo =
    signalType === "tech-stack" ? getTechSummary(signal) : null;
  const summaryText = techInfo ? techInfo.name : signal.summary;
  const techSecondary = techInfo
    ? signal.usage_scope_display || formatContact(getContact(signal))
    : null;

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

      <Box sx={{ flex: 1, overflow: "hidden", minWidth: 0 }}>
        <Typography
          variant="body2"
          sx={{
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {truncate(summaryText)}
        </Typography>
        {techSecondary && (
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              display: "block",
            }}
          >
            {techSecondary}
          </Typography>
        )}
      </Box>

      <SignalStatusChip status={signal.status} size="small" />

      {techInfo?.pending && (
        <Chip
          icon={<WarningOutlined style={{ fontSize: 10 }} />}
          label="Not in catalog"
          size="small"
          color="warning"
          variant="outlined"
          sx={{ height: 20, fontSize: "0.7rem" }}
        />
      )}

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
    tech_name: PropTypes.string,
    metadata: PropTypes.object,
  }).isRequired,
  signalType: PropTypes.oneOf(["pain", "objective", "impact", "tech-stack"])
    .isRequired,
  onSelect: PropTypes.func,
  onValidate: PropTypes.func,
  onReject: PropTypes.func,
  isLocked: PropTypes.bool,
};
