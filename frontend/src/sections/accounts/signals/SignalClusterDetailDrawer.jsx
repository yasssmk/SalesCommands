// frontend/src/sections/accounts/signals/SignalClusterDetailDrawer.jsx
/**
 * SignalClusterDetailDrawer — drill-down view for a Pain cluster.
 *
 * Opens on click of a SignalClusterCard. Displays:
 *   - Header with cluster identity, priority, freshness, stats
 *   - Archive / unarchive action in the header
 *   - A panel of rich aggregated stats (metrics, linked DCs, human impacts)
 *   - The cluster's member signals as PainCards with full CRUD
 *
 * Self-contained modal state
 * --------------------------
 * The drawer owns its own dialogs (AddPainImpactDialog, SignalEditDialog,
 * AlertSignalReject) and routes the PainCard callbacks to them. This keeps
 * the parent (AccountSignalsTab) thin — it only needs to provide accountId,
 * choices, and a callback when something happens so it can revalidate its
 * own cluster list.
 *
 * Cache flow
 * ----------
 * Any signal/impact mutation from the members revalidates the shared
 * "pain" and "pain-impacts" caches (handled by painImpacts.js /
 * signals.js). Since the cluster endpoint shares the same backend cache
 * tag, the drawer's own cluster detail fetch automatically refreshes on
 * next focus or next mutation. We also call mutateCluster() explicitly
 * for immediate UI feedback after each action.
 */

"use client";

import PropTypes from "prop-types";
import { useCallback, useMemo, useState } from "react";

// material-ui
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// ant-design icons
import AlertOutlined from "@ant-design/icons/AlertOutlined";
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import InboxOutlined from "@ant-design/icons/InboxOutlined";
import UndoOutlined from "@ant-design/icons/UndoOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";
import UserOutlined from "@ant-design/icons/UserOutlined";

// project imports
import PainCard from "components/cards/signals/PainCard";
import AddPainImpactDialog from "./pain/AddPainImpactDialog";
import AlertSignalReject from "./AlertSignalReject";
import SignalEditDialog from "./SignalEditDialog";

import {
  useGetClusterDetail,
  archiveCluster,
  unarchiveCluster,
} from "api/signals/signalClusters";
import { validateSignal, deleteSignal } from "api/signals/signals";
import { deletePainImpact } from "api/signals/painImpacts";
import {
  displayErrorSnackbar,
  displaySuccessSnackbar,
} from "utils/displayError";

import {
  resolveFreshness,
  resolveHumanImpact,
  resolveImpactLevel,
  resolvePriority,
} from "sections/accounts/signals/signalClusters";

// ==============================|| CONSTANTS ||============================== //

/**
 * Drawer width — responsive.
 * xs (mobile) full-width, sm/md tablet ~560px, lg+ 640px for comfortable
 * nested PainCard reading without feeling cramped.
 */
const DRAWER_WIDTH = { xs: "100%", sm: 560, md: 640 };

// ==============================|| HELPERS ||============================== //

function formatShortDate(iso) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return null;
  }
}

// ==============================|| STAT CELL ||============================== //

/**
 * Small labelled stat cell used in the stats grid at the top of the body.
 *
 * value handling
 * --------------
 * MUI Typography defaults its HTML element to <p> for body/caption variants.
 * If we unconditionally wrap the `value` prop in <Typography>, any caller
 * passing a nested <Typography> (e.g. styled fallback) or any component that
 * itself renders a <p> would produce invalid <p><p>…</p></p> markup and
 * trigger a hydration error.
 *
 * We therefore:
 *   - wrap primitive values (string/number) in a <Typography> for consistent
 *     style with other cells;
 *   - render composite values (Chip, custom node) directly so callers can
 *     style them as they wish.
 */
function StatCell({ label, value, hint }) {
  const isPrimitiveValue =
    typeof value === "string" || typeof value === "number";

  return (
    <Stack spacing={0.25}>
      <Typography variant="caption" color="text.disabled" fontWeight={500}>
        {label}
      </Typography>

      {isPrimitiveValue ? (
        <Typography variant="body1" fontWeight={600}>
          {value}
        </Typography>
      ) : (
        value
      )}

      {hint && (
        <Typography variant="caption" color="text.disabled">
          {hint}
        </Typography>
      )}
    </Stack>
  );
}

StatCell.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.node.isRequired,
  hint: PropTypes.string,
};

// ==============================|| DRAWER ||============================== //

/**
 * SignalClusterDetailDrawer
 *
 * @param {boolean}  open              - Drawer open state
 * @param {Function} onClose           - () => void
 * @param {Object}   clusterSummary    - Cluster list item (has canonical_key,
 *                                        used to trigger the detail fetch).
 *                                        May be null when drawer is closed.
 * @param {string}   accountId         - Account UUID
 * @param {Object}   choices           - From useGetSignalChoices()
 * @param {boolean}  choicesLoading
 * @param {Function} onClusterChange   - () => void — notifies the parent that
 *                                        it should revalidate its list
 *                                        (archive, unarchive, member edits).
 */
export default function SignalClusterDetailDrawer({
  open,
  onClose,
  clusterSummary,
  accountId,
  choices,
  choicesLoading,
  onClusterChange,
}) {
  // ==============================|| DETAIL FETCH ||============================== //

  const canonicalKey = clusterSummary?.canonical_key ?? null;
  const signalType = clusterSummary?.signal_type ?? "pain";

  const { cluster, clusterLoading, clusterError, mutateCluster } =
    useGetClusterDetail(accountId, canonicalKey, { signalType });

  // ==============================|| DERIVED ||============================== //

  // While the detail is loading for the first time, we rely on the list
  // summary payload to render the header so the drawer doesn't flash empty.
  const display = cluster ?? clusterSummary ?? null;

  const isArchived = Boolean(display?.is_archived);
  const freshness = resolveFreshness(display?.freshness_status);
  const priority = resolvePriority(display?.priority_bucket);
  const maxLevel = resolveImpactLevel(display?.max_impact_level);

  const FreshnessIcon = freshness.icon;
  const PriorityIcon = priority.icon;

  const canonicalText = useMemo(() => {
    if (!display?.what_display || !display?.dimension_display) return null;
    return `${display.what_display} × ${display.dimension_display}`;
  }, [display?.what_display, display?.dimension_display]);

  const firstObservedDate = formatShortDate(display?.first_observed_at);
  const lastConfirmedDate = formatShortDate(display?.last_confirmed_at);

  /** Deduplicated member signals coming from the detail payload. */
  const members = useMemo(
    () => (Array.isArray(cluster?.members) ? cluster.members : []),
    [cluster?.members],
  );

  /** Metrics — free-text list from all VALIDATED impacts. */
  const metrics = useMemo(
    () => (Array.isArray(display?.metrics) ? display.metrics : []),
    [display?.metrics],
  );

  /** Human impacts — aggregated by type, sorted desc by count. */
  const humanImpacts = useMemo(
    () => (Array.isArray(display?.human_impacts) ? display.human_impacts : []),
    [display?.human_impacts],
  );

  /** Linked decision cycle count. */
  const linkedCyclesCount = Array.isArray(display?.decision_cycle_ids)
    ? display.decision_cycle_ids.length
    : 0;

  // ==============================|| LOCAL STATE (modals) ||============================== //

  const [editModal, setEditModal] = useState({
    open: false,
    signal: null,
    signalType: null,
  });

  const [rejectModal, setRejectModal] = useState({
    open: false,
    signal: null,
    signalType: null,
  });

  const [impactDialog, setImpactDialog] = useState({
    open: false,
    mode: null,
    painSignalId: null,
    initialImpact: null,
  });

  const [archivalSubmitting, setArchivalSubmitting] = useState(false);

  // ==============================|| REVALIDATION ||============================== //

  /**
   * Called after any mutation that changes the cluster's underlying data.
   * - Revalidates THIS drawer's detail fetch
   * - Notifies the parent so it can revalidate its listing
   */
  const notifyChange = useCallback(() => {
    mutateCluster?.();
    onClusterChange?.();
  }, [mutateCluster, onClusterChange]);

  // ==============================|| ARCHIVE / UNARCHIVE ||============================== //

  const handleArchive = useCallback(async () => {
    if (!canonicalKey || !accountId) return;
    setArchivalSubmitting(true);
    const result = await archiveCluster({
      account: accountId,
      canonicalKey,
      signalType,
    });
    setArchivalSubmitting(false);
    if (result.success) {
      displaySuccessSnackbar("Cluster archived");
      notifyChange();
    } else {
      displayErrorSnackbar(result);
    }
  }, [accountId, canonicalKey, signalType, notifyChange]);

  const handleUnarchive = useCallback(async () => {
    if (!canonicalKey || !accountId) return;
    setArchivalSubmitting(true);
    const result = await unarchiveCluster({
      account: accountId,
      canonicalKey,
      signalType,
    });
    setArchivalSubmitting(false);
    if (result.success) {
      displaySuccessSnackbar("Cluster unarchived");
      notifyChange();
    } else {
      displayErrorSnackbar(result);
    }
  }, [accountId, canonicalKey, signalType, notifyChange]);

  // ==============================|| MEMBER LIFECYCLE HANDLERS ||============================== //

  const handleValidate = useCallback(
    async (signal, type) => {
      const result = await validateSignal(type, signal.id);
      if (result.success) {
        notifyChange();
        displaySuccessSnackbar("Signal validated");
      } else {
        displayErrorSnackbar(result);
      }
    },
    [notifyChange],
  );

  const handleRejectOpen = useCallback((signal, type) => {
    setRejectModal({ open: true, signal, signalType: type });
  }, []);

  const handleRejectClose = useCallback(() => {
    setRejectModal({ open: false, signal: null, signalType: null });
  }, []);

  const handleRejectSuccess = useCallback(() => {
    setRejectModal({ open: false, signal: null, signalType: null });
    notifyChange();
    displaySuccessSnackbar("Signal rejected");
  }, [notifyChange]);

  const handleEdit = useCallback((signal, type) => {
    setEditModal({ open: true, signal, signalType: type });
  }, []);

  const handleEditClose = useCallback(() => {
    setEditModal({ open: false, signal: null, signalType: null });
  }, []);

  const handleEditSuccess = useCallback(() => {
    notifyChange();
  }, [notifyChange]);

  const handleDelete = useCallback(
    async (signal, type) => {
      const result = await deleteSignal(type, signal.id);
      if (result.success) {
        notifyChange();
        displaySuccessSnackbar("Signal deleted");
      } else {
        displayErrorSnackbar(result);
      }
    },
    [notifyChange],
  );

  // ==============================|| IMPACT HANDLERS ||============================== //

  const handleAddImpact = useCallback((painSignalId) => {
    setImpactDialog({
      open: true,
      mode: "create",
      painSignalId,
      initialImpact: null,
    });
  }, []);

  const handleEditImpact = useCallback((impact) => {
    setImpactDialog({
      open: true,
      mode: "edit",
      painSignalId: null,
      initialImpact: impact,
    });
  }, []);

  const handleImpactDialogClose = useCallback(() => {
    setImpactDialog({
      open: false,
      mode: null,
      painSignalId: null,
      initialImpact: null,
    });
  }, []);

  const handleImpactDialogSuccess = useCallback(() => {
    notifyChange();
    displaySuccessSnackbar("Impact saved");
  }, [notifyChange]);

  const handleDeleteImpact = useCallback(
    async (impact) => {
      const result = await deletePainImpact(impact.id);
      if (result.success) {
        notifyChange();
        displaySuccessSnackbar("Impact deleted");
      } else {
        displayErrorSnackbar(result);
      }
    },
    [notifyChange],
  );

  // ==============================|| RENDER: HEADER ||============================== //

  const renderHeader = () => (
    <Box sx={{ px: 2.5, pt: 2, pb: 1.5 }}>
      {/* Top row: close button */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="flex-start"
        sx={{ mb: 1 }}
      >
        <Stack
          direction="row"
          spacing={0.75}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
        >
          <Chip
            label="Pain"
            color="error"
            size="small"
            variant="outlined"
            sx={{ fontSize: "0.68rem", height: 20 }}
          />

          {display?.priority_bucket && (
            <Tooltip
              title={`Priority score: ${display?.priority_score ?? "—"}`}
            >
              <Chip
                icon={<PriorityIcon style={{ fontSize: 11 }} />}
                label={priority.label}
                color={priority.color}
                variant={priority.variant}
                size="small"
                sx={{ fontSize: "0.68rem", height: 20 }}
              />
            </Tooltip>
          )}

          {display?.freshness_status && (
            <Tooltip title={freshness.helperText}>
              <Chip
                icon={<FreshnessIcon style={{ fontSize: 11 }} />}
                label={freshness.label}
                color={freshness.color}
                size="small"
                variant="outlined"
                sx={{ fontSize: "0.68rem", height: 20 }}
              />
            </Tooltip>
          )}

          {isArchived && (
            <Chip
              icon={<InboxOutlined style={{ fontSize: 11 }} />}
              label="Archived"
              size="small"
              sx={{ fontSize: "0.68rem", height: 20 }}
            />
          )}
        </Stack>

        <IconButton
          size="small"
          onClick={onClose}
          aria-label="Close drawer"
          sx={{ ml: 1, flexShrink: 0 }}
        >
          <CloseOutlined style={{ fontSize: 14 }} />
        </IconButton>
      </Stack>

      {/* Canonical axes title */}
      {canonicalText && (
        <Typography variant="h6" fontWeight={600} sx={{ mt: 0.5 }}>
          {canonicalText}
        </Typography>
      )}

      {/* Consolidated summary */}
      {display?.summary && (
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ mt: 0.75, whiteSpace: "pre-wrap" }}
        >
          {display.summary}
        </Typography>
      )}

      {/* Pending alert */}
      {display?.has_pending_signals && display?.pending_count > 0 && (
        <Stack
          direction="row"
          spacing={0.75}
          alignItems="center"
          sx={{
            mt: 1.5,
            py: 0.75,
            px: 1,
            bgcolor: "warning.lighter",
            borderRadius: 0.75,
            border: "1px dashed",
            borderColor: "warning.light",
          }}
        >
          <AlertOutlined style={{ fontSize: 12, color: "#faad14" }} />
          <Typography variant="caption" color="warning.dark" fontWeight={500}>
            {display.pending_count} signal
            {display.pending_count === 1 ? "" : "s"} need
            {display.pending_count === 1 ? "s" : ""} validation below
          </Typography>
        </Stack>
      )}

      {/* Archive / unarchive actions */}
      <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
        {!isArchived ? (
          <Button
            size="small"
            variant="outlined"
            color="inherit"
            startIcon={<InboxOutlined />}
            onClick={handleArchive}
            disabled={archivalSubmitting || !canonicalKey}
          >
            Archive cluster
          </Button>
        ) : (
          <Button
            size="small"
            variant="outlined"
            color="primary"
            startIcon={<UndoOutlined />}
            onClick={handleUnarchive}
            disabled={archivalSubmitting || !canonicalKey}
          >
            Unarchive cluster
          </Button>
        )}
      </Stack>
    </Box>
  );

  // ==============================|| RENDER: STATS PANEL ||============================== //

  const renderStats = () => (
    <Paper
      variant="outlined"
      sx={{
        mx: 2.5,
        mb: 2,
        p: 2,
        borderRadius: 1.5,
        bgcolor: "background.default",
      }}
    >
      {/* Top row: 4 stat cells */}
      <Stack
        direction="row"
        spacing={3}
        flexWrap="wrap"
        useFlexGap
        sx={{ mb: 1.5 }}
      >
        <StatCell
          label="Max level"
          value={
            display?.max_impact_level ? (
              <Chip
                label={maxLevel.label}
                color={maxLevel.color}
                size="small"
                variant="outlined"
                sx={{ fontSize: "0.68rem", height: 20 }}
              />
            ) : (
              "—"
            )
          }
        />
        <StatCell
          label="Impacted contacts"
          value={display?.impacted_contacts_count ?? 0}
        />
        <StatCell
          label="Max level"
          value={
            display?.max_impact_level ? (
              <Chip
                label={maxLevel.label}
                color={maxLevel.color}
                size="small"
                variant="outlined"
                sx={{ fontSize: "0.68rem", height: 20 }}
              />
            ) : (
              <Typography variant="body2" color="text.disabled">
                —
              </Typography>
            )
          }
        />
        <StatCell label="Decision cycles" value={linkedCyclesCount} />
      </Stack>

      {/* Lifecycle row */}
      <Stack
        direction="row"
        spacing={3}
        flexWrap="wrap"
        useFlexGap
        sx={{ mb: humanImpacts.length || metrics.length ? 1.5 : 0 }}
      >
        {firstObservedDate && (
          <StatCell label="First observed" value={firstObservedDate} />
        )}
        {lastConfirmedDate && (
          <StatCell label="Last confirmed" value={lastConfirmedDate} />
        )}
      </Stack>

      {/* Human impacts */}
      {humanImpacts.length > 0 && (
        <Stack spacing={0.75} sx={{ mb: metrics.length ? 1.5 : 0 }}>
          <Typography variant="caption" color="text.disabled" fontWeight={500}>
            Human impacts
          </Typography>
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
            {humanImpacts.map((entry) => {
              const cfg = resolveHumanImpact(entry.type);
              return (
                <Chip
                  key={entry.type}
                  label={`${cfg.label} ×${entry.count}`}
                  size="small"
                  variant="outlined"
                  sx={{ fontSize: "0.68rem", height: 20 }}
                />
              );
            })}
          </Stack>
        </Stack>
      )}

      {/* Metrics */}
      {metrics.length > 0 && (
        <Stack spacing={0.75}>
          <Typography variant="caption" color="text.disabled" fontWeight={500}>
            Metrics observed
          </Typography>
          <Stack spacing={0.25}>
            {metrics.map((metric, idx) => (
              // Metrics are free-text — index is acceptable as key since the
              // list is stable for a given cluster read and we don't reorder.
              // eslint-disable-next-line react/no-array-index-key
              <Typography
                key={`${idx}-${metric.slice(0, 20)}`}
                variant="body2"
                color="text.secondary"
                sx={{ pl: 1, borderLeft: "2px solid", borderColor: "divider" }}
              >
                {metric}
              </Typography>
            ))}
          </Stack>
        </Stack>
      )}
    </Paper>
  );

  // ==============================|| RENDER: MEMBERS ||============================== //

  const renderMembers = () => {
    // Header with count
    return (
      <Box sx={{ px: 2.5, pb: 3 }}>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
          <Typography variant="subtitle2" fontWeight={600}>
            Signals in this cluster
          </Typography>
          {members.length > 0 && (
            <Chip
              label={members.length}
              size="small"
              variant="outlined"
              sx={{ height: 18, fontSize: "0.62rem" }}
            />
          )}
        </Stack>

        {clusterLoading && !cluster && (
          <Stack alignItems="center" py={3}>
            <CircularProgress size={20} />
          </Stack>
        )}

        {clusterError && (
          <Stack alignItems="center" spacing={1} py={3}>
            <AlertOutlined style={{ fontSize: 24, color: "#ff4d4f" }} />
            <Typography variant="body2" color="error">
              Failed to load cluster details.
            </Typography>
          </Stack>
        )}

        {cluster && members.length === 0 && (
          <Typography
            variant="body2"
            color="text.disabled"
            sx={{ fontStyle: "italic", py: 1.5 }}
          >
            No signals to display. All previous members may have been deleted or
            rejected.
          </Typography>
        )}

        {members.length > 0 && (
          <Stack spacing={1.5}>
            {members.map((member) => (
              <PainCard
                key={member.id}
                pain={member}
                choices={choices}
                onValidate={handleValidate}
                onReject={handleRejectOpen}
                onEdit={handleEdit}
                onDelete={handleDelete}
                onAddImpact={handleAddImpact}
                onEditImpact={handleEditImpact}
                onDeleteImpact={handleDeleteImpact}
              />
            ))}
          </Stack>
        )}
      </Box>
    );
  };

  // ==============================|| RENDER ||============================== //

  return (
    <>
      <Drawer
        anchor="right"
        open={open}
        onClose={onClose}
        PaperProps={{
          sx: {
            width: DRAWER_WIDTH,
            maxWidth: "100vw",
          },
        }}
      >
        {!clusterSummary ? (
          // No cluster provided — safe guard, should not happen in practice
          // because the parent only opens the drawer after setting the summary.
          <Stack alignItems="center" justifyContent="center" sx={{ py: 8 }}>
            <CircularProgress size={24} />
          </Stack>
        ) : (
          <>
            {renderHeader()}
            <Divider />
            <Box sx={{ pt: 2 }}>{renderStats()}</Box>
            <Divider sx={{ mx: 2.5 }} />
            <Box sx={{ pt: 2 }}>{renderMembers()}</Box>
          </>
        )}
      </Drawer>

      {/* ==================== MEMBER MODALS ==================== */}

      <SignalEditDialog
        open={editModal.open}
        onClose={handleEditClose}
        onSuccess={handleEditSuccess}
        signal={editModal.signal}
        signalType={editModal.signalType}
        accountId={accountId}
        choices={choices}
        choicesLoading={choicesLoading}
      />

      <AlertSignalReject
        open={rejectModal.open}
        onClose={handleRejectClose}
        onSuccess={handleRejectSuccess}
        signal={rejectModal.signal}
        signalType={rejectModal.signalType}
      />

      <AddPainImpactDialog
        open={impactDialog.open}
        onClose={handleImpactDialogClose}
        onSuccess={handleImpactDialogSuccess}
        painSignalId={impactDialog.painSignalId}
        accountId={accountId}
        initialImpact={impactDialog.initialImpact}
      />
    </>
  );
}

// ==============================|| PROP TYPES ||============================== //

SignalClusterDetailDrawer.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  clusterSummary: PropTypes.shape({
    canonical_key: PropTypes.string.isRequired,
    signal_type: PropTypes.string,
    // Other fields optional — the drawer fetches full detail.
  }),
  accountId: PropTypes.string.isRequired,
  choices: PropTypes.object,
  choicesLoading: PropTypes.bool,
  onClusterChange: PropTypes.func,
};

SignalClusterDetailDrawer.defaultProps = {
  clusterSummary: null,
  choices: null,
  choicesLoading: false,
  onClusterChange: () => {},
};
