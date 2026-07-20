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
import useDecisionCycleFilters from "hooks/useDecisionCycleFilters";

// api
import {
  useGetDecisionCycles,
  buildUrlWithParams,
  CYCLE_DERIVED_STATUS_LABELS,
  CYCLE_STATUS_COLORS,
} from "api/accounts/decisionCycles";
import { useKpiBatch } from "api/bi/kpi";
import { tenantKey } from "api/_swr";

// utils
import { formatDateTime } from "config/formatters";

// ==============================|| CONSTANTS ||============================== //

const ENDPOINT = "/decision_cycles/";

/**
 * Map frontend column ids to backend ordering field names. Only columns the
 * backend can order on are listed (DecisionCycleViewSet.ordering_fields =
 * name, is_active, created_at, updated_at). KPI-derived and to-one display
 * columns are not server-sortable.
 */
const COLUMN_TO_BACKEND_FIELD = {
  name: "name",
  updated_at: "updated_at",
};

const STATUS_LABELS = {
  OPEN: "Open",
  WON: "Won",
  LOST: "Lost",
  ON_HOLD: "On Hold",
  NOT_QUALIFIED: "Not Qualified",
};

const OWNER_SCOPE_LABELS = { mine: "Mine", team: "My Team" };

// STALLED reads as a caution in the shared palette ('warning'); the Home block
// forces it red as the "act now" lever. Mirror that override so both surfaces
// agree, without mutating the shared CYCLE_STATUS_COLORS.
const STATUS_COLOR = { ...CYCLE_STATUS_COLORS, STALLED: "error" };

// ==============================|| AMOUNT FORMAT ||============================== //

/**
 * Format estimated_value for display. No currency code on the model, so the raw
 * decimal is shown grouped with two fraction digits; null → dash.
 */
function formatAmount(value) {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return "—";
  return n.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

// ==============================|| DECISION CYCLES LIST PAGE ||============================== //

/**
 * Decision Cycles admin list — read-only table under Business Data.
 *
 * Structurally identical to the Account list (views/businessData/accounts):
 * ReusableTable + the funnel-icon advanced filter drawer + filter chips. Only
 * the columns, data and facets differ. No tabs.
 *
 * Data model (same mechanic as the Home DC block):
 *   - name / account / owner / team / outcome / estimated_value / updated_at
 *     come from the list serializer (useGetDecisionCycles).
 *   - stage / derived status come from the dc_cycle_state KPI, one request per
 *     visible cycle, batched via useKpiBatch and zipped by index.
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

  // ==============================|| KPI ENRICHMENT (dc_cycle_state) ||============================== //

  // dc_cycle_state allowed_scopes are ('mine','team','client'); the list's
  // 'all' maps to the KPI's 'client'.
  const kpiScope = filters.owner_scope === "all" ? "client" : filters.owner_scope;

  const kpiRequests = useMemo(
    () =>
      cycles.map((c) => ({
        key: "dc_cycle_state",
        scope: kpiScope,
        params: { cycle_id: c.id },
      })),
    [cycles, kpiScope],
  );

  const { results: kpiResults = [] } = useKpiBatch(kpiRequests, {
    enabled: cycles.length > 0,
  });

  // Enrich each cycle row with its KPI meta, zipped by index (as the Home does).
  const rows = useMemo(
    () =>
      cycles.map((c, i) => {
        const res = kpiResults[i];
        const meta = res?.meta || {};
        const derivedStatus = res?.value || meta.cycle_status || null;
        return {
          ...c,
          stage_name: meta.current_step_name || null,
          derived_status: derivedStatus,
        };
      }),
    [cycles, kpiResults],
  );

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
      // owner_scope is removed by widening to 'all' (its non-narrowing value).
      updatePendingFilter(
        filterKey,
        filterKey === "owner_scope" ? "all" : filterKey === "account" ? null : "",
      );
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
        label: "Owner",
        value: OWNER_SCOPE_LABELS[filters.owner_scope] || filters.owner_scope,
      });
    }
    if (filters.account?.id) {
      chips.push({
        key: "account",
        label: "Account",
        value: filters.account.company_name || "Selected",
      });
    }
    if (filters.status) {
      chips.push({
        key: "status",
        label: "Status",
        value: STATUS_LABELS[filters.status] || filters.status,
      });
    }
    return chips;
  }, [filters]);

  // ==============================|| COLUMNS ||============================== //

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
        enableSorting: false,
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

      // Owner (name, email fallback — names are nullable on User)
      {
        header: "Owner",
        accessorKey: "owner_name",
        enableSorting: false,
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
        enableSorting: false,
        cell: ({ getValue }) => (
          <Typography variant="body2" color="text.secondary">
            {getValue()?.name || "—"}
          </Typography>
        ),
      },

      // Stage (KPI: current step name)
      {
        header: "Stage",
        accessorKey: "stage_name",
        enableSorting: false,
        cell: ({ getValue }) => (
          <Typography variant="body2" color="text.secondary">
            {getValue() || "—"}
          </Typography>
        ),
      },

      // Amount (estimated_value)
      {
        header: "Amount",
        accessorKey: "estimated_value",
        meta: { className: "cell-right" },
        enableSorting: false,
        cell: ({ getValue }) => (
          <Typography variant="body2">{formatAmount(getValue())}</Typography>
        ),
      },

      // Status — outcome when closed, KPI-derived status when open
      {
        header: "Status",
        id: "status",
        enableSorting: false,
        cell: ({ row }) => {
          const { outcome, derived_status: derived } = row.original;
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
        data={rows}
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
