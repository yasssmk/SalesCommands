// frontend/src/sections/activities/signals/SignalsFlatView.jsx

"use client";

import PropTypes from "prop-types";
import { useMemo, useState, useEffect } from "react";

// MUI
import Box from "@mui/material/Box";
import Pagination from "@mui/material/Pagination";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import { ThunderboltOutlined } from "@ant-design/icons";

// Project imports
import SignalLine from "components/signals/SignalLine";

// ==============================|| SORT HELPERS ||============================== //

const TYPE_ORDER = ["pain", "objective", "impact", "tech-stack", "blockers"];
const STATUS_ORDER = { PENDING: 0, VALIDATED: 1, REJECTED: 2 };

const PAGE_SIZE = 20;

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

/**
 * Shared flat renderer for the three signal surfaces (Activity / DC / Account).
 * Renders each signal as a compact SignalLine and paginates the list at
 * PAGE_SIZE (20) per page over whatever array the parent passes — an
 * aggregated mixed list on Activity/DC, a single-type list on Account.
 *
 * Clicking a line calls onSelect so the parent opens the signal drawer.
 */
export default function SignalsFlatView({
  signals,
  sortKey,
  onSelect,
  onValidate,
  onReject,
  onEdit,
  onReopen,
  isLocked,
  emptyMessage = "No signals found for this activity",
}) {
  const sortedSignals = useMemo(
    () => sortSignals(signals, sortKey),
    [signals, sortKey],
  );

  const totalPages = Math.ceil(sortedSignals.length / PAGE_SIZE);
  const [page, setPage] = useState(1);

  // Keep the current page in range when the list shrinks (filter/sort change).
  useEffect(() => {
    if (page > totalPages && totalPages > 0) setPage(totalPages);
    if (totalPages === 0 && page !== 1) setPage(1);
  }, [page, totalPages]);

  const pageSignals = useMemo(
    () => sortedSignals.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    [sortedSignals, page],
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
            {emptyMessage}
          </Typography>
        </Stack>
      </Box>
    );
  }

  return (
    <Box>
      {pageSignals.map((signal) => (
        <SignalLine
          key={signal.id}
          signal={signal}
          signalType={signal._signalType}
          onSelect={onSelect}
          onValidate={onValidate}
          onReject={onReject}
          onEdit={onEdit}
          onReopen={onReopen}
          isLocked={isLocked}
        />
      ))}

      {totalPages > 1 && (
        <Stack direction="row" justifyContent="center" sx={{ mt: 2 }}>
          <Pagination
            count={totalPages}
            page={page}
            onChange={(e, next) => setPage(next)}
            showFirstButton
            showLastButton
            color="primary"
            size="small"
          />
        </Stack>
      )}
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
  onSelect: PropTypes.func,
  onValidate: PropTypes.func,
  onReject: PropTypes.func,
  onEdit: PropTypes.func,
  onReopen: PropTypes.func,
  isLocked: PropTypes.bool,
  emptyMessage: PropTypes.string,
};
