// frontend/src/components/chips/SignalTypeChip.jsx

"use client";

import PropTypes from "prop-types";
import Chip from "@mui/material/Chip";

// Icons
import {
  WarningOutlined,
  AimOutlined,
  ThunderboltOutlined,
  ToolOutlined,
  StopOutlined,
  ScheduleOutlined,
} from "@ant-design/icons";

const TYPE_CONFIG = {
  pain: { color: "error", label: "Pain", Icon: WarningOutlined },
  objective: { color: "info", label: "Objective", Icon: AimOutlined },
  impact: { color: "warning", label: "Impact", Icon: ThunderboltOutlined },
  "tech-stack": { color: "primary", label: "Tech Stack", Icon: ToolOutlined },
  blockers: { color: "default", label: "Blocker", Icon: StopOutlined },
  "next-steps": { color: "secondary", label: "Next Step", Icon: ScheduleOutlined },
};

// ==============================|| SIGNAL TYPE CHIP ||============================== //

export default function SignalTypeChip({
  signalType,
  size = "small",
  ...rest
}) {
  const config = TYPE_CONFIG[signalType];
  if (!config) return null;

  const { Icon, label, color } = config;

  return (
    <Chip
      icon={<Icon style={{ fontSize: 12 }} />}
      label={label}
      color={color}
      size={size}
      variant="outlined"
      {...rest}
    />
  );
}

SignalTypeChip.propTypes = {
  signalType: PropTypes.oneOf([
    "pain",
    "objective",
    "impact",
    "tech-stack",
    "blockers",
    "next-steps",
  ]),
  size: PropTypes.oneOf(["small", "medium"]),
};
