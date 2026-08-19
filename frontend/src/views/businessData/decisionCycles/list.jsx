// src/views/businessData/decisionCycles/list.jsx
"use client";

import { useMemo, useState, useCallback } from "react";
import { useRouter } from "next/navigation";

// material-ui
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";

// project imports
import ReusableTable from "components/table/Table";
import DecisionCycleFilterPanel from "sections/businessData/decisionCycles/DecisionCycleFilterPanel";

// hooks
import useLocalStorage from "hooks/useLocalStorage";
import { useAuth } from "hooks/useAuth";
import useDecisionCycleFilters, {
  OBJECT_FACETS,
} from "hooks/useDecisionCycleFilters";

// api
import {
  useGetDecisionCycles,
  buildUrlWithParams,
  CYCLE_DERIVED_STATUS_LABELS,
  CYCLE_STATUS_COLORS,
} from "api/accounts/decisionCycles";
import { tenantKey } from "api/_swr";

// utils
import { formatDateTime } from "config/formatters";
import formatAmount from "utils/formatAmount";

// ==============================|| CONSTANTS ||============================== //

const ENDPOINT = "/decision_cycles/";

/**
 * Map each column's TanStack id to the backend ordering field. All eight
 * columns are server-sortable (DecisionCycleViewSet.ordering_fields): flat
 * fields, FK traversals, and the 1b annotations for stage / effective status.
 */
const COLUMN_TO_BACKEND_FIELD = {
  cycle_name: "name",
  account_name: "account__company_name",
  current_step_name: "_current_step_stage", // Stage column: sort by the stage annotation
  status: "_cycle_effective_status",
  total_deal_value: "_deal_value", // Amount: sort on the roll-up annotation
  owner_name: "owner__first_name",
  team: "owner__team__name",
  updated_at: "updated_at",
};

const STATUS_LABELS = {
  OPEN: "Open",
  WON: "Won",
  LOST: "Lost",
  ON_HOLD: "On Hold",
  NOT_QUALIFIED: "Not Qualified",
  NOT_STARTED: "Not Started",
  IN_PROGRESS: "In Progress",
  OVERDUE: "Overdue",
  STALLED: "Stalled",
};

const OWNER_SCOPE_LABELS = { mine: "Mine", team: "My Team" };

// Readable chip value for an object-valued facet.
const facetChipValue = {
  account: (o) => o.company_name || o.name || "Selected",
  owner: (o) =>
    `${o.first_name || ""} ${o.last_name || ""}`.trim() || o.email || "Selected",
  team: (o) => o.name || "Selected",
  contact: (o) =>
    `${o.first_name || ""} ${o.last_name || ""}`.trim() || o.name || "Selected",
  source_campaign: (o) => o.name || "Selected",
  product: (o) => o.name || "Selected",
};

const FACET_CHIP_LABEL = {
  account: "Account",
  owner: "Owner",
  team: "Team",
  contact: "Contact",
  source_campaign: "Campaign",
  product: "Product",
};

// STALLED reads as a caution in the shared palette ('warning'); the Home block
// forces it red as the "act now" lever. Mirror that override so both surfaces
// agree, without mutating the shared CYCLE_STATUS_COLORS.
const STATUS_COLOR = { ...CYCLE_STATUS_COLORS, STALLED: "error" };

// ==============================|| DECISION CYCLES LIST PAGE ||============================== //

/**
 * Decision Cycles admin list — read-only table under Business Data.
 *
 * Structurally identical to the Account list (views/businessData/accounts):
 * ReusableTable + the funnel-icon advanced filter drawer + filter chips. Only
 * the columns, data and facets differ. No tabs.
 *
 * Data model: every column — including the effective status (cycle_status) and
 * the current step (current_step_name) — is served by the list serializer
 * (useGetDecisionCycles). The view no longer makes a per-row dc_cycle_state KPI
 * call; that KPI still backs the Home blocks, just not this table.
 *
 * Read-only: no create, no bulk, no multi-select, no import. Clicking the
 * cycle name opens /accounts/{account}/dc/{id} (the shared table has no
 * row-level onClick, so the primary cell carries the navigation).
 */
export default function DecisionCyclesListPage() {
  const { tenantId } = useAuth();
  const router = useRouter();
  const MAX_PAGE_SIZE = 100;

  // ==============================|| STATE ||============================== //

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useLocalStorage(
    "decisionCyclesTablePageSize",
    10,
  );

  const validPageSize = useMemo(() => {
    const parsed = Number(pageSize);
    if (isNaN(parsed) || parsed <= 0) return 10;
    return Math.min(parsed, MAX_PAGE_SIZE);
  }, [pageSize]);

  const [search, setSearch] = useState("");
  const [sorting, setSorting] = useState([]);
  const [filterPanelOpen, setFilterPanelOpen] = useState(false);

  // Advanced filters hook (Account pattern)
  const {
    filters,
    pendingFilters,
    activeFiltersCount,
    hasPendingChanges,
    apiFilters,
    updatePendingFilter,
    updatePendingFilters,
    applyFilters,
    clearFilters,
    resetPendingFilters,
  } = useDecisionCycleFilters();

  // ==============================|| ORDERING ||============================== //

  const ordering = useMemo(() => {
    if (!Array.isArray(sorting) || sorting.length === 0) {
      return ""; // backend default (-is_active, -updated_at)
    }
    return sorting
      .map(({ id, desc }) => {
        const backendField = COLUMN_TO_BACKEND_FIELD[id] || id;
        return desc ? `-${backendField}` : backendField;
      })
      .join(",");
  }, [sorting]);

  // ==============================|| LIST DATA ||============================== //

  const {
    cycles = [],
    cyclesCount = 0,
    cyclesLoading = false,
    cyclesError = null,
  } = useGetDecisionCycles({
    page,
    pageSize: validPageSize,
    search,
    ordering,
    filters: apiFilters,
  });

  const swrKey = useMemo(
    () =>
      tenantKey(
        buildUrlWithParams(ENDPOINT, {
          page,
          pageSize: validPageSize,
          search,
          ordering,
          filters: apiFilters,
        }),
        tenantId,
      ),
    [page, validPageSize, search, ordering, apiFilters, tenantId],
  );

  // Stage and effective status now come straight from the list serializer
  // (cycle_status / current_stage / current_step_name), so the per-row
  // dc_cycle_state KPI call this view used to make is gone. The rows are the
  // serializer records as-is.

  // ==============================|| HANDLERS ||============================== //

  const handlePaginationChange = useCallback(
    ({ page: newPage, pageSize: newPageSize }) => {
      setPage(newPage);
      const size = Number(newPageSize);
      if (!isNaN(size) && size > 0 && size !== validPageSize) {
        setPageSize(size);
      }
    },
    [setPageSize, validPageSize],
  );

  const handleSearchChange = useCallback((searchTerm) => {
    setSearch(searchTerm);
    setPage(1);
  }, []);

  const handleSortingChange = useCallback((updaterOrValue) => {
    setSorting((prev) => {
      const next =
        typeof updaterOrValue === "function"
          ? updaterOrValue(prev)
          : updaterOrValue;
      if (JSON.stringify(next) !== JSON.stringify(prev)) {
        setPage(1);
      }
      return next;
    });
  }, []);

  const goToCycle = useCallback(
    (cycle) => {
      // account is the account id on the list serializer; id is the cycle id.
      router.push(`/accounts/${cycle.account}/dc/${cycle.id}`);
    },
    [router],
  );

  const goToAccount = useCallback(
    (cycle) => {
      router.push(`/accounts/${cycle.account}`);
    },
    [router],
  );

  // ==============================|| FILTER HANDLERS (Account pattern) ||============================== //

  const handleOpenFilterPanel = useCallback(() => {
    setFilterPanelOpen(true);
  }, []);

  const handleCloseFilterPanel = useCallback(() => {
    resetPendingFilters();
    setFilterPanelOpen(false);
  }, [resetPendingFilters]);

  const handleApplyFilters = useCallback(() => {
    applyFilters();
    setPage(1);
    setFilterPanelOpen(false);
  }, [applyFilters]);

  const handleClearFilters = useCallback(() => {
    clearFilters();
    setPage(1);
  }, [clearFilters]);

  const handleRemoveFilter = useCallback(
    (filterKey) => {
      // Neutral value per facet type: owner_scope widens to 'all', object facets
      // reset to null, the status string resets to ''.
      const neutral =
        filterKey === "owner_scope"
          ? "all"
          : OBJECT_FACETS.includes(filterKey)
            ? null
            : "";
      updatePendingFilter(filterKey, neutral);
      setTimeout(() => {
        applyFilters();
        setPage(1);
      }, 0);
    },
    [updatePendingFilter, applyFilters],
  );

  // ==============================|| FILTER CHIPS ||============================== //

  const advancedFiltersChips = useMemo(() => {
    const chips = [];
    if (filters.owner_scope && filters.owner_scope !== "all") {
      chips.push({
        key: "owner_scope",
        label: "Owner scope",
        value: OWNER_SCOPE_LABELS[filters.owner_scope] || filters.owner_scope,
      });
    }
    if (filters.status) {
      chips.push({
        key: "status",
        label: "Status",
        value: STATUS_LABELS[filters.status] || filters.status,
      });
    }
    // Object-valued facets — one removable chip each, with a readable value.
    for (const key of OBJECT_FACETS) {
      const obj = filters[key];
      if (obj?.id) {
        chips.push({
          key,
          label: FACET_CHIP_LABEL[key],
          value: facetChipValue[key](obj),
        });
      }
    }
    return chips;
  }, [filters]);

  // ==============================|| COLUMNS ||============================== //

  // Column order: name · account · stage · status · amount · owner · team ·
  // last updated. All eight are server-sortable (COLUMN_TO_BACKEND_FIELD maps
  // each id to its ordering field). Stage and status come from the serializer
  // (current_step_name / cycle_status), no longer from the KPI.
  const columns = useMemo(
    () => [
      // Decision cycle name — primary, clickable → cycle workspace
      {
        header: "Decision Cycle",
        accessorKey: "cycle_name",
        cell: ({ row, getValue }) => (
          <Typography
            variant="subtitle1"
            sx={{
              cursor: "pointer",
              "&:hover": {
                color: "primary.main",
                textDecoration: "underline",
              },
            }}
            onClick={(e) => {
              e.stopPropagation();
              goToCycle(row.original);
            }}
          >
            {getValue() || "Decision cycle"}
          </Typography>
        ),
      },

      // Account — clickable → account workspace (same link style as the name)
      {
        header: "Account",
        accessorKey: "account_name",
        cell: ({ row, getValue }) => (
          <Typography
            variant="body2"
            sx={{
              cursor: "pointer",
              "&:hover": {
                color: "primary.main",
                textDecoration: "underline",
              },
            }}
            onClick={(e) => {
              e.stopPropagation();
              goToAccount(row.original);
            }}
          >
            {getValue() || "Account"}
          </Typography>
        ),
      },

      // Stage — current step name (serializer: current_step_name), sorted by the
      // current-step stage annotation.
      {
        header: "Stage",
        accessorKey: "current_step_name",
        cell: ({ getValue }) => (
          <Typography variant="body2" color="text.secondary">
            {getValue() || "—"}
          </Typography>
        ),
      },

      // Status — outcome when closed, derived effective status (serializer:
      // cycle_status) when open. Sorted by the effective-status annotation.
      {
        header: "Status",
        id: "status",
        // accessorFn (not just a cell) so the column is sortable — a display
        // column with no accessor reports getCanSort() === false. Sorting maps
        // `status` → _cycle_effective_status (COLUMN_TO_BACKEND_FIELD).
        accessorFn: (row) => row.cycle_status,
        cell: ({ row }) => {
          const { outcome, cycle_status: derived } = row.original;
          const statusKey = outcome || derived; // closed → outcome, open → derived
          if (!statusKey) {
            return (
              <Typography variant="body2" color="text.secondary">
                —
              </Typography>
            );
          }
          const label = CYCLE_DERIVED_STATUS_LABELS[statusKey] || statusKey;
          const color = STATUS_COLOR[statusKey] || "default";
          return (
            <Chip size="small" label={label} color={color} variant="light" />
          );
        },
      },

      // Amount — the DERIVED product roll-up (total_deal_value), rendered with
      // the tenant currency. NOT estimated_value: that manual field is never
      // populated, so this column used to show a dash on every row (TD-75).
      {
        header: "Amount",
        accessorKey: "total_deal_value",
        meta: { className: "cell-right" },
        cell: ({ getValue, row }) => (
          <Typography variant="body2">
            {formatAmount(getValue(), row.original.currency)}
          </Typography>
        ),
      },

      // Owner (name, email fallback — names are nullable on User)
      {
        header: "Owner",
        accessorKey: "owner_name",
        cell: ({ row }) => (
          <Typography variant="body2">
            {row.original.owner_name || row.original.owner_email || "—"}
          </Typography>
        ),
      },

      // Team
      {
        header: "Team",
        accessorKey: "team",
        cell: ({ getValue }) => (
          <Typography variant="body2" color="text.secondary">
            {getValue()?.name || "—"}
          </Typography>
        ),
      },

      // Last update
      {
        header: "Last Updated",
        accessorKey: "updated_at",
        cell: ({ getValue }) => {
          const v = getValue();
          return (
            <Typography variant="body2" color="text.secondary">
              {v ? formatDateTime(v) : "Never"}
            </Typography>
          );
        },
      },
    ],
    [goToCycle, goToAccount],
  );

  // ==============================|| RENDER ||============================== //

  return (
    <>
      <ReusableTable
        data={cycles}
        columns={columns}
        loading={cyclesLoading}
        error={cyclesError}
        swrKey={swrKey}
        totalCount={cyclesCount}
        currentPage={page}
        onPaginationChange={handlePaginationChange}
        onSearchChange={handleSearchChange}
        sorting={sorting}
        onSortingChange={handleSortingChange}
        initialPageSize={validPageSize}
        // Read-only: no create, no import
        showAddButton={false}
        enableImport={false}
        searchPlaceholder={`Search ${cyclesCount} decision cycles...`}
        exportFilename="decision-cycles.csv"
        emptyMessage="No decision cycles found"
        emptyDescription="Decision cycles are created from an account"
        // Advanced Filter Panel (funnel icon + drawer) — Account pattern
        advancedFilterPanel={
          <DecisionCycleFilterPanel
            open={filterPanelOpen}
            onClose={handleCloseFilterPanel}
            pendingFilters={pendingFilters}
            onFilterChange={updatePendingFilter}
            onFiltersChange={updatePendingFilters}
            onApply={handleApplyFilters}
            onClear={handleClearFilters}
            hasPendingChanges={hasPendingChanges}
            matchingCount={cyclesCount}
            loading={cyclesLoading}
          />
        }
        advancedFilters={advancedFiltersChips}
        advancedFilterCount={activeFiltersCount}
        onAdvancedFilterOpen={handleOpenFilterPanel}
        onAdvancedFilterRemove={handleRemoveFilter}
        onAdvancedFilterClear={handleClearFilters}
      />
    </>
  );
}
