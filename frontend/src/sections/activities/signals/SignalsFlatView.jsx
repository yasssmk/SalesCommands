// frontend/src/sections/activities/signals/SignalsFlatView.jsx

"use client";

import PropTypes from "prop-types";
import { useMemo } from "react";

// MUI
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import { ThunderboltOutlined } from "@ant-design/icons";

// Project imports
import SignalDetailCard from "components/cards/signals/SignalDetailCard";

// ==============================|| SORT HELPERS ||============================== //

const TYPE_ORDER = ["pain", "objective", "impact", "tech-stack", "blockers"];
const STATUS_ORDER = { PENDING: 0, VALIDATED: 1, REJECTED: 2 };

function sortSignals(signals, sortKey) {
  const sorted = [...signals];

  switch (sortKey) {
    case "date-desc":
      return sorted.sort(
        (a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0),
      );

    case "date-asc":
      return sorted.sort(
        (a, b) => new Date(a.created_at || 0) - new Date(b.created_at || 0),
      );

    case "type":
      return sorted.sort((a, b) => {
        const ai = TYPE_ORDER.indexOf(a._signalType);
        const bi = TYPE_ORDER.indexOf(b._signalType);
        return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
      });

    case "theme": {
      return sorted.sort((a, b) => {
        const aTheme = a.what_display && a.dimension_display
          ? `${a.what_display} × ${a.dimension_display}`
          : "zzz";
        const bTheme = b.what_display && b.dimension_display
          ? `${b.what_display} × ${b.dimension_display}`
          : "zzz";
        return aTheme.localeCompare(bTheme);
      });
    }

    case "status":
      return sorted.sort(
        (a, b) =>
          (STATUS_ORDER[a.status] ?? 3) - (STATUS_ORDER[b.status] ?? 3),
      );

    default:
      return sorted;
  }
}

// ==============================|| SIGNALS FLAT VIEW ||============================== //

export default function SignalsFlatView({
  signals,
  sortKey,
  onValidate,
  onReject,
  onEdit,
  isLocked,
}) {
  const sortedSignals = useMemo(
    () => sortSignals(signals, sortKey),
    [signals, sortKey],
  );

  if (!sortedSignals.length) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="200px"
      >
        <Stack spacing={1} alignItems="center" textAlign="center">
          <ThunderboltOutlined style={{ fontSize: 36, color: "#8c8c8c" }} />
          <Typography variant="body2" color="text.secondary">
            No signals found for this activity
          </Typography>
        </Stack>
      </Box>
    );
  }

  return (
    <Box>
      {sortedSignals.map((signal) => (
        <SignalDetailCard
          key={signal.id}
          signal={signal}
          signalType={signal._signalType}
          onValidate={onValidate}
          onReject={onReject}
          onEdit={onEdit}
          isLocked={isLocked}
        />
      ))}
    </Box>
  );
}

SignalsFlatView.propTypes = {
  signals: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      _signalType: PropTypes.string.isRequired,
    }),
  ).isRequired,
  sortKey: PropTypes.oneOf(["date-desc", "date-asc", "type", "theme", "status"]),
  onValidate: PropTypes.func,
  onReject: PropTypes.func,
  onEdit: PropTypes.func,
  isLocked: PropTypes.bool,
};
