// frontend/src/sections/accounts/workspace/AccountQualificationTab.jsx
/**
 * AccountQualificationTab — strategic cluster view for an account.
 *
 * Renders all signal clusters (Pain + Objective) for the account in a
 * unified, priority-ordered list. The tab is a read-only / archive-only
 * surface: signals are created and edited in the Signals tab; this tab
 * exists for the rep to scan "what matters here, right now".
 *
 * Data flow
 * ---------
 *   - useGetClustersByAccount with mixed signalType (pain + objective)
 *     by default, narrows to a single type when the user filters.
 *   - useGetSignalChoices is fetched once and forwarded to the drawer
 *     (the drawer's nested PainCard / ObjectiveCard need it for axis
 *     labels and the impact dialog).
 *
 * Filters
 * -------
 *   - Type      (Tous / Pain / Objective)   — server-side via signalType
 *   - HIGH only (off / on)                  — client-side post-fetch
 *   - Archived  (hide / show)               — server-side via includeArchived
 *
 * The tab does NOT support a search input or DC filter in MVP — those
 * are tracked as later-sprint work.
 *
 * Cluster mutations (archive / unarchive) revalidate the cluster cache
 * via the API layer; the drawer also handles signal-level mutations
 * for its own member cards (validate / reject / edit / delete) and
 * notifies us via onClusterChange so we can refresh our list.
 */

"use client";

import PropTypes from "prop-types";
import { useCallback, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";

// material-ui
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import FormControlLabel from "@mui/material/FormControlLabel";
import Skeleton from "@mui/material/Skeleton";
import Stack from "@mui/material/Stack";
import Switch from "@mui/material/Switch";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";

// ant-design icons
import AlertOutlined from "@ant-design/icons/AlertOutlined";
import InboxOutlined from "@ant-design/icons/InboxOutlined";
import ThunderboltOutlined from "@ant-design/icons/ThunderboltOutlined";

// project imports
import SignalClusterCard from "components/cards/signals/SignalClusterCard";
import SignalClusterDetailDrawer from "../signals/SignalClusterDetailDrawer";

import {
  useGetClustersByAccount,
  archiveCluster,
  unarchiveCluster,
} from "api/signals/signalClusters";
import { useGetSignalChoices } from "api/signals/signals";
import {
  displayErrorSnackbar,
  displaySuccessSnackbar,
} from "utils/displayError";

// ==============================|| CONSTANTS ||============================== //

/**
 * Type filter options. The internal value is what the toggle stores;
 * `signalTypePayload` is what we send to the API hook.
 *
 * 'all' translates to a CSV array so the backend returns clusters of
 * all clustered types in a single call, server-sorted by priority.
 *
 * Sprint TechStack — Tech Stack joins the cluster surface
 * -------------------------------------------------------
 * The TechStack cluster uses the canonical key "techstack:<entry.id>"
 * (see SignalClusterService). Mixed lists therefore stay key-unique
 * across types thanks to the per-type prefix. The card key in the
 * render loop combines signal_type + canonical_key, which already
 * disambiguates any future collisions.
 *
 * Note on the 'all' payload: we send the new type as 'tech_stack'
 * (snake_case, mirror of cluster.signal_type from the backend payload).
 * This is intentionally distinct from the URL-style 'tech-stack'
 * (kebab-case) used in SignalList / AccountSignalsTab, because the
 * backend cluster API and the underscore-style enum are aligned.
 */
const TYPE_FILTER_OPTIONS = [
  {
    value: "all",
    label: "All",
    signalTypePayload: ["pain", "objective", "tech_stack"],
  },
  { value: "pain", label: "Pain", signalTypePayload: "pain" },
  { value: "objective", label: "Objective", signalTypePayload: "objective" },
  { value: "tech_stack", label: "Tech Stack", signalTypePayload: "tech_stack" },
];

const TYPE_FILTER_BY_VALUE = TYPE_FILTER_OPTIONS.reduce((acc, opt) => {
  acc[opt.value] = opt;
  return acc;
}, {});

// ==============================|| EMPTY STATE ||============================== //

/**
 * Empty state shown when the account has no clusters at all (or none
 * matching the current filters).
 *
 * The CTA navigates to the Signals tab so the rep can capture their
 * first signals via the wizard. Once at least one signal exists for the
 * account on a canonical key, a cluster will surface here automatically.
 */
function ClusterEmptyState({ hasFilters, onGoToSignals }) {
  return (
    <Stack alignItems="center" py={6} spacing={1.5}>
      <InboxOutlined style={{ fontSize: 36, color: "#bfbfbf" }} />
      <Typography variant="body1" color="text.secondary" fontWeight={500}>
        {hasFilters
          ? "No clusters match the current filters"
          : "No qualification clusters yet"}
      </Typography>
      <Typography
        variant="body2"
        color="text.disabled"
        textAlign="center"
        maxWidth={420}
      >
        {hasFilters
          ? "Try removing the priority or archived filter, or switch to another type."
          : "Pain, Objective and Tech Stack signals captured during conversations group automatically into priority clusters here."}
      </Typography>
      {!hasFilters && (
        <Button
          size="small"
          variant="outlined"
          color="primary"
          onClick={onGoToSignals}
        >
          Go to Signals tab
        </Button>
      )}
    </Stack>
  );
}

ClusterEmptyState.propTypes = {
  hasFilters: PropTypes.bool.isRequired,
  onGoToSignals: PropTypes.func.isRequired,
};

// ==============================|| LOADING SKELETON ||============================== //

function ClusterListSkeleton() {
  return (
    <Stack spacing={1.5}>
      <Skeleton variant="rounded" height={200} />
      <Skeleton variant="rounded" height={200} />
      <Skeleton variant="rounded" height={200} />
    </Stack>
  );
}

// ==============================|| ERROR STATE ||============================== //

function ClusterErrorState() {
  return (
    <Stack alignItems="center" spacing={1} py={6}>
      <AlertOutlined style={{ fontSize: 32, color: "#ff4d4f" }} />
      <Typography variant="body2" color="error">
        Failed to load clusters. Please refresh and try again.
      </Typography>
    </Stack>
  );
}

// ==============================|| ACCOUNT QUALIFICATION TAB ||============================== //

/**
 * AccountQualificationTab
 *
 * @param {string} accountId - Account UUID (required)
 */
export default function AccountQualificationTab({ accountId }) {
  const router = useRouter();
  const params = useParams();

  // ==============================|| FILTER STATE ||============================== //

  const [typeFilter, setTypeFilter] = useState("all");
  const [highOnly, setHighOnly] = useState(false);
  const [includeArchived, setIncludeArchived] = useState(false);

  // ==============================|| DATA FETCHING ||============================== //

  /**
   * The signalType payload depends on the current type filter.
   * Memoised on the filter value so the API hook's cache key stays
   * stable across renders.
   */
  const signalTypePayload = useMemo(
    () => TYPE_FILTER_BY_VALUE[typeFilter].signalTypePayload,
    [typeFilter],
  );

  const { clusters, clustersLoading, clustersError, mutateClusters } =
    useGetClustersByAccount(accountId, {
      signalType: signalTypePayload,
      includeArchived,
    });

  // Choices forwarded to the drawer (PainCard / ObjectiveCard / impact
  // dialog need axis labels). Single tenant-wide fetch.
  const { choices, choicesLoading } = useGetSignalChoices();

  // ==============================|| CLIENT-SIDE FILTERING ||============================== //

  /**
   * HIGH-only filter is applied here, after the server response.
   * The backend's sort order (priority_score desc, then last_confirmed_at)
   * is preserved by Array.prototype.filter, so the visual ordering is
   * stable when toggling the filter.
   */
  const visibleClusters = useMemo(() => {
    if (!highOnly) return clusters;
    return clusters.filter((c) => c.priority_bucket === "HIGH");
  }, [clusters, highOnly]);

  /**
   * Whether any filter is active (other than the default state).
   * Drives the empty-state copy: "no clusters yet" vs "no clusters
   * match these filters".
   */
  const hasActiveFilters = useMemo(
    () => typeFilter !== "all" || highOnly || includeArchived,
    [typeFilter, highOnly, includeArchived],
  );

  // ==============================|| DRAWER STATE ||============================== //

  const [drawerState, setDrawerState] = useState({
    open: false,
    clusterSummary: null,
  });

  const handleClusterClick = useCallback((cluster) => {
    setDrawerState({ open: true, clusterSummary: cluster });
  }, []);

  const handleDrawerClose = useCallback(() => {
    setDrawerState({ open: false, clusterSummary: null });
  }, []);

  /**
   * Called by the drawer whenever a mutation changes cluster data
   * (archive, unarchive, member validation, member edit, impact CRUD).
   * The drawer revalidates its own detail internally — we just need to
   * refresh the list.
   */
  const handleClusterChange = useCallback(() => {
    mutateClusters();
  }, [mutateClusters]);

  // ==============================|| CARD ACTIONS ||============================== //

  const handleArchiveFromCard = useCallback(
    async (cluster) => {
      const result = await archiveCluster({
        account: accountId,
        canonicalKey: cluster.canonical_key,
        signalType: cluster.signal_type,
      });
      if (result.success) {
        mutateClusters();
        displaySuccessSnackbar("Cluster archived");
      } else {
        displayErrorSnackbar(result);
      }
    },
    [accountId, mutateClusters],
  );

  const handleUnarchiveFromCard = useCallback(
    async (cluster) => {
      const result = await unarchiveCluster({
        account: accountId,
        canonicalKey: cluster.canonical_key,
        signalType: cluster.signal_type,
      });
      if (result.success) {
        mutateClusters();
        displaySuccessSnackbar("Cluster unarchived");
      } else {
        displayErrorSnackbar(result);
      }
    },
    [accountId, mutateClusters],
  );

  // ==============================|| FILTER HANDLERS ||============================== //

  const handleTypeFilterChange = useCallback((_e, newValue) => {
    if (newValue !== null) setTypeFilter(newValue);
  }, []);

  const handleHighOnlyChange = useCallback((e) => {
    setHighOnly(e.target.checked);
  }, []);

  const handleIncludeArchivedChange = useCallback((e) => {
    setIncludeArchived(e.target.checked);
  }, []);

  // ==============================|| NAVIGATION ||============================== //

  /**
   * Redirect to the Signals tab. The page-level route is
   * /accounts/{id}?tab={tab} — see views/accounts/workspace/index.jsx.
   * Using router.push (vs router.replace) preserves browser history
   * so the rep can come back to Qualification with the back button.
   */
  const handleGoToSignals = useCallback(() => {
    const id = params?.id ?? accountId;
    router.push(`/accounts/${id}?tab=signals`, { scroll: false });
  }, [router, params, accountId]);

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      {/* ==================== TOOLBAR ==================== */}
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={1.5}
        alignItems={{ xs: "stretch", sm: "center" }}
        justifyContent="space-between"
        sx={{ mb: 2 }}
      >
        {/* Left: type toggle.
            With the 4th option added (Tech Stack), the row gets denser —
            we tighten horizontal padding so the toggle still fits the
            sm/md toolbar without forcing the priority+archived switches
            on a second row at common widths. */}
        <ToggleButtonGroup
          value={typeFilter}
          exclusive
          onChange={handleTypeFilterChange}
          size="small"
          aria-label="Filter clusters by type"
          sx={{ flexShrink: 0 }}
        >
          {TYPE_FILTER_OPTIONS.map((opt) => (
            <ToggleButton
              key={opt.value}
              value={opt.value}
              sx={{ textTransform: "none", px: 1.25, fontSize: "0.78rem" }}
            >
              {opt.label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>

        {/* Right: priority + archived switches */}
        <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={highOnly}
                onChange={handleHighOnlyChange}
                inputProps={{ "aria-label": "Show high priority only" }}
              />
            }
            label={
              <Stack direction="row" spacing={0.5} alignItems="center">
                <ThunderboltOutlined style={{ fontSize: 12 }} />
                <Typography variant="caption" color="text.secondary">
                  High only
                </Typography>
              </Stack>
            }
            sx={{ m: 0 }}
          />
          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={includeArchived}
                onChange={handleIncludeArchivedChange}
                inputProps={{ "aria-label": "Show archived clusters" }}
              />
            }
            label={
              <Stack direction="row" spacing={0.5} alignItems="center">
                <InboxOutlined style={{ fontSize: 12 }} />
                <Typography variant="caption" color="text.secondary">
                  Show archived
                </Typography>
              </Stack>
            }
            sx={{ m: 0 }}
          />
        </Stack>
      </Stack>

      <Divider sx={{ mb: 2 }} />

      {/* ==================== CLUSTER LIST ==================== */}
      {clustersLoading && <ClusterListSkeleton />}

      {!clustersLoading && clustersError && <ClusterErrorState />}

      {!clustersLoading && !clustersError && visibleClusters.length === 0 && (
        <ClusterEmptyState
          hasFilters={hasActiveFilters}
          onGoToSignals={handleGoToSignals}
        />
      )}

      {!clustersLoading && !clustersError && visibleClusters.length > 0 && (
        <Stack spacing={1.5}>
          {visibleClusters.map((cluster) => (
            <SignalClusterCard
              // canonical_key is unique per (account, signal_type) and
              // signal_type changes the visual identity, so combining
              // both prevents key collisions when mixed types share an
              // axis pair (e.g. pain:GROWTH:COST + objective:GROWTH:COST).
              key={`${cluster.signal_type}:${cluster.canonical_key}`}
              cluster={cluster}
              onClick={handleClusterClick}
              onArchive={handleArchiveFromCard}
              onUnarchive={handleUnarchiveFromCard}
            />
          ))}

          {/* Footer count chip — mirrors AccountSignalsTab's pattern */}
          <Stack direction="row" justifyContent="flex-end" sx={{ pt: 0.5 }}>
            <Chip
              label={`${visibleClusters.length} cluster${
                visibleClusters.length === 1 ? "" : "s"
              }`}
              size="small"
              variant="outlined"
              sx={{ fontSize: "0.7rem" }}
            />
          </Stack>
        </Stack>
      )}

      {/* ==================== DRAWER ==================== */}
      <SignalClusterDetailDrawer
        open={drawerState.open}
        onClose={handleDrawerClose}
        clusterSummary={drawerState.clusterSummary}
        accountId={accountId}
        choices={choices}
        choicesLoading={choicesLoading}
        onClusterChange={handleClusterChange}
      />
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

AccountQualificationTab.propTypes = {
  accountId: PropTypes.string.isRequired,
};
