// frontend/src/sections/activities/signals/SignalsFlatView.jsx

"use client";

import PropTypes from "prop-types";
import { useMemo, useState, useEffect } from "react";

// MUI
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
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
 * Renders each signal as a compact SignalLine.
 *
 * Two modes:
 *  - CLIENT (default): sorts by `sortKey` and paginates the given array at
 *    PAGE_SIZE (20) per page in the component.
 *  - SERVER (`serverPaginated`): the parent already fetched one server page
 *    (sorted + sliced by the aggregated endpoint). This view renders it as
 *    given and drives the Pagination control from `page` / `pageCount` /
 *    `onPageChange`; it shows a loading spinner while a page fetches.
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
  // Server-pagination mode (optional):
  serverPaginated = false,
  page: serverPage,
  pageCount: serverPageCount,
  onPageChange,
  loading = false,
}) {
  const sortedSignals = useMemo(
    () => (serverPaginated ? signals : sortSignals(signals, sortKey)),
    [serverPaginated, signals, sortKey],
  );

  const [clientPage, setClientPage] = useState(1);

  const totalPages = serverPaginated
    ? serverPageCount ?? 1
    : Math.ceil(sortedSignals.length / PAGE_SIZE);
  const currentPage = serverPaginated ? serverPage ?? 1 : clientPage;

  // Client mode: keep the current page in range when the list shrinks.
  useEffect(() => {
    if (serverPaginated) return;
    if (clientPage > totalPages && totalPages > 0) setClientPage(totalPages);
    if (totalPages === 0 && clientPage !== 1) setClientPage(1);
  }, [serverPaginated, clientPage, totalPages]);

  const pageSignals = useMemo(
    () =>
      serverPaginated
        ? sortedSignals
        : sortedSignals.slice((clientPage - 1) * PAGE_SIZE, clientPage * PAGE_SIZE),
    [serverPaginated, sortedSignals, clientPage],
  );

  // Loading a page (server mode) with nothing to show yet → spinner.
  if (serverPaginated && loading && !sortedSignals.length) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
        <CircularProgress size={28} />
      </Box>
    );
  }

  if (!sortedSignals.length) {
    // Business-empty is information, not an error (neutral tone).
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

  const handlePageChange = (e, next) => {
    if (serverPaginated) onPageChange?.(next);
    else setClientPage(next);
  };

  return (
    <Box sx={{ position: "relative" }}>
      {/* Subtle overlay while re-fetching a different page in server mode. */}
      {serverPaginated && loading && (
        <Box
          sx={{
            position: "absolute", top: 0, right: 0,
            p: 1, zIndex: 1,
          }}
        >
          <CircularProgress size={18} />
        </Box>
      )}

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
        <Stack spacing={2} sx={{ p: 2.5 }} alignItems="flex-end">
          <Pagination
            sx={{ "& .MuiPaginationItem-root": { my: 0.5 } }}
            count={totalPages}
            size="medium"
            page={currentPage}
            showFirstButton
            showLastButton
            variant="combined"
            color="primary"
            onChange={handlePageChange}
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
  // Server-pagination mode
  serverPaginated: PropTypes.bool,
  page: PropTypes.number,
  pageCount: PropTypes.number,
  onPageChange: PropTypes.func,
  loading: PropTypes.bool,
};
