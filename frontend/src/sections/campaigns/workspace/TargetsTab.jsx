// frontend/src/sections/campaigns/workspace/TargetsTab.jsx

import { useState, useMemo, useCallback } from "react";
import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// Icons
import PauseCircleOutlined from "@ant-design/icons/PauseCircleOutlined";
import PlayCircleOutlined from "@ant-design/icons/PlayCircleOutlined";
import PlusOutlined from "@ant-design/icons/PlusOutlined";
import StopOutlined from "@ant-design/icons/StopOutlined";
import DeleteOutlined from "@ant-design/icons/DeleteOutlined";
import WarningFilled from "@ant-design/icons/WarningFilled";

// Project
import ReusableTable from "components/table/Table";
import AddTargetToCampaignModal from "./AddTargetToCampaignModal";
import {
  useGetCampaignContacts,
  pauseTarget,
  removeTargets,
  resumeTarget,
  stopTarget,
} from "api/campaigns/campaigns";

import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// ==============================|| CONSTANTS ||============================== //

const CONTACT_STATUS_CONFIG = {
  PENDING: { label: "Pending", color: "default" },
  IN_PROGRESS: { label: "In Progress", color: "info" },
  CALLBACK_PENDING: { label: "Callback Pending", color: "warning" },
  COMPLETED: { label: "Completed", color: "success" },
  STOPPED: { label: "Stopped", color: "error" },
};

// Final contact states — mirrors the backend FINAL_CONTACT_STATES frozenset
// (campaigns/constants.py). A paused (ON_HOLD) or callback-pending contact is
// NOT final: it is still being chased and stays under "In progress".
const FINAL_CONTACT_STATUSES = ["COMPLETED", "STOPPED"];

// Binary chasing-status filter for the Target tab. "Active" shows the contacts
// still being chased (the 4 non-final states); "All" shows everyone — a finished
// contact is recognised by its existing status chip, no dedicated view needed.
// Applied CLIENT-SIDE: the contacts endpoint is unpaginated and the full set is
// already in the SWR cache, so a server round-trip per toggle would only add a
// spinner for no benefit.

// ==============================|| TARGETS TAB ||============================== //

export default function TargetsTab({ campaignId, campaign }) {
  const isFinal =
    campaign?.status === "COMPLETED" || campaign?.status === "CANCELLED";

  // ==============================|| DATA ||============================== //

  const {
    campaignContacts,
    campaignContactsLoading,
    campaignContactsError,
    mutateCampaignContacts,
  } = useGetCampaignContacts(campaignId);

  // ==============================|| LOCAL STATE ||============================== //

  const [search, setSearch] = useState("");
  // Default gated on campaign type: TARGETED starts on "Active" (the chase in
  // progress); OUTBOUND starts on "All" (the filter has no meaning in prospecting).
  const [statusFilter, setStatusFilter] = useState(() =>
    campaign?.campaign_type === "TARGETED" ? "active" : "all",
  );
  const [sorting, setSorting] = useState([]);
  const [selectedRows, setSelectedRows] = useState(new Set());
  const [actionInProgress, setActionInProgress] = useState(null);
  const [confirmRemove, setConfirmRemove] = useState(null);
  // confirmRemove: null | { ids: string[], label: string }
  const [confirmStop, setConfirmStop] = useState(null);
  // confirmStop: null | campaignContact — the contact awaiting Stop confirmation.
  // Stop is irreversible from this view (Reactivate is gone; re-chasing means
  // re-enrolling via Add Target), so it is gated behind a confirmation.

  const [addTargetOpen, setAddTargetOpen] = useState(false);

  const isTargeted = campaign?.campaign_type === "TARGETED";

  // For TARGETED: exclude only contacts still being chased (non-final states).
  // COMPLETED/STOPPED contacts stay selectable in the Add Target modal so they
  // can be re-enrolled — enrolling a finished contact re-chases it.
  // For non-TARGETED: exclude all currently enrolled contacts.
  const enrolledContactIds = useMemo(() => {
    if (isTargeted) {
      return campaignContacts
        .filter((cc) =>
          ["IN_PROGRESS", "PENDING", "ON_HOLD", "CALLBACK_PENDING"].includes(
            cc.status,
          ),
        )
        .map((cc) => cc.contact?.id || cc.contact)
        .filter(Boolean);
    }
    return campaignContacts
      .map((cc) => cc.contact?.id || cc.contact)
      .filter(Boolean);
  }, [campaignContacts, isTargeted]);
  const handleSortingChange = useCallback((updaterOrValue) => {
    setSorting((prev) =>
      typeof updaterOrValue === "function"
        ? updaterOrValue(prev)
        : updaterOrValue,
    );
  }, []);

  // ==============================|| STATUS + SEARCH FILTER ||============================== //

  const filteredContacts = useMemo(() => {
    const q = search.trim().toLowerCase();
    return campaignContacts.filter((cc) => {
      // Chasing-status filter (client-side). "Active" excludes only the two
      // final states; "All" excludes nothing.
      if (
        statusFilter === "active" &&
        FINAL_CONTACT_STATUSES.includes(cc.status)
      ) {
        return false;
      }

      // Free-text search.
      if (!q) return true;
      const name = (cc.contact_name || "").toLowerCase();
      const account = (cc.account_name || "").toLowerCase();
      const dept = (cc.contact?.department_name || "").toLowerCase();
      return name.includes(q) || account.includes(q) || dept.includes(q);
    });
  }, [campaignContacts, search, statusFilter]);

  // ==============================|| SELECTION ||============================== //

  const allSelected =
    filteredContacts.length > 0 &&
    filteredContacts.every((cc) => selectedRows.has(cc.id));

  const someSelected =
    !allSelected && filteredContacts.some((cc) => selectedRows.has(cc.id));

  const handleSelectAll = useCallback(() => {
    if (allSelected) {
      setSelectedRows(new Set());
    } else {
      setSelectedRows(new Set(filteredContacts.map((cc) => cc.id)));
    }
  }, [allSelected, filteredContacts]);

  const handleSelectRow = useCallback((id) => {
    setSelectedRows((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }, []);

  // ==============================|| ROW ACTIONS ||============================== //

  const handlePauseRow = useCallback(
    async (cc) => {
      setActionInProgress({ type: "pause", id: cc.id });
      try {
        const result = await pauseTarget(cc.id, campaignId);
        if (result.success) {
          displaySuccessSnackbar("Contact sequence paused");
          mutateCampaignContacts();
        } else {
          displayErrorSnackbar(result);
        }
      } catch (err) {
        displayErrorSnackbar(err);
      } finally {
        setActionInProgress(null);
      }
    },
    [campaignId, mutateCampaignContacts],
  );

  const handleResumeRow = useCallback(
    async (cc) => {
      setActionInProgress({ type: "resume", id: cc.id });
      try {
        const result = await resumeTarget(cc.id, campaignId);
        if (result.success) {
          displaySuccessSnackbar("Contact sequence resumed");
          mutateCampaignContacts();
        } else {
          displayErrorSnackbar(result);
        }
      } catch (err) {
        displayErrorSnackbar(err);
      } finally {
        setActionInProgress(null);
      }
    },
    [campaignId, mutateCampaignContacts],
  );

  const handleRowRemove = useCallback((cc) => {
    setConfirmRemove({
      ids: [cc.id],
      label: cc.contact_name || "this contact",
    });
  }, []);

  // Open the Stop confirmation for a row. The actual stop runs only from
  // handleConfirmStop → handleStopRow (the single stopTarget caller).
  const requestStop = useCallback((cc) => {
    setConfirmStop(cc);
  }, []);

  const handleStopRow = useCallback(
    async (cc) => {
      setActionInProgress({ type: "stop", id: cc.id });
      try {
        const result = await stopTarget(cc.id, campaignId);
        if (result.success) {
          displaySuccessSnackbar("Contact sequence stopped");
          mutateCampaignContacts();
        } else {
          displayErrorSnackbar(result);
        }
      } catch (err) {
        displayErrorSnackbar(err);
      } finally {
        setActionInProgress(null);
      }
    },
    [campaignId, mutateCampaignContacts],
  );

  const handleConfirmStop = useCallback(() => {
    if (!confirmStop) return;
    const cc = confirmStop;
    setConfirmStop(null);
    handleStopRow(cc);
  }, [confirmStop, handleStopRow]);

  // ==============================|| BULK ACTIONS ||============================== //

  const handleBulkRemove = useCallback(() => {
    const ids = [...selectedRows];
    if (!ids.length) return;
    setConfirmRemove({ ids, label: `${ids.length} contact(s)` });
  }, [selectedRows]);

  const handleConfirmRemove = useCallback(async () => {
    if (!confirmRemove) return;
    const { ids } = confirmRemove;
    setConfirmRemove(null);
    setActionInProgress({ type: "remove", id: "bulk" });
    try {
      const result = await removeTargets(campaignId, ids);
      if (result.success) {
        displaySuccessSnackbar(`${ids.length} contact(s) removed`);
        setSelectedRows(new Set());
        mutateCampaignContacts();
      } else {
        displayErrorSnackbar(result);
      }
    } catch (err) {
      displayErrorSnackbar(err);
    } finally {
      setActionInProgress(null);
    }
  }, [confirmRemove, campaignId, mutateCampaignContacts]);

  const handleBulkPause = useCallback(async () => {
    const ids = [...selectedRows];
    if (!ids.length) return;
    setActionInProgress({ type: "pause", id: "bulk" });
    try {
      await Promise.allSettled(ids.map((id) => pauseTarget(id, campaignId)));
      displaySuccessSnackbar(`${ids.length} contact(s) paused`);
      setSelectedRows(new Set());
      mutateCampaignContacts();
    } catch (err) {
      displayErrorSnackbar(err);
    } finally {
      setActionInProgress(null);
    }
  }, [selectedRows, campaignId, mutateCampaignContacts]);

  const handleBulkResume = useCallback(async () => {
    const ids = [...selectedRows];
    if (!ids.length) return;
    setActionInProgress({ type: "resume", id: "bulk" });
    try {
      await Promise.allSettled(ids.map((id) => resumeTarget(id, campaignId)));
      displaySuccessSnackbar(`${ids.length} contact(s) resumed`);
      setSelectedRows(new Set());
      mutateCampaignContacts();
    } catch (err) {
      displayErrorSnackbar(err);
    } finally {
      setActionInProgress(null);
    }
  }, [selectedRows, campaignId, mutateCampaignContacts]);

  // ==============================|| COLUMNS ||============================== //

  const columns = useMemo(
    () => [
      // Checkbox
      {
        id: "select",
        header: () => (
          <input
            type="checkbox"
            checked={allSelected}
            ref={(el) => {
              if (el) el.indeterminate = someSelected;
            }}
            onChange={handleSelectAll}
          />
        ),
        cell: ({ row }) => (
          <input
            type="checkbox"
            checked={selectedRows.has(row.original.id)}
            onChange={() => handleSelectRow(row.original.id)}
            onClick={(e) => e.stopPropagation()}
          />
        ),
        enableSorting: false,
        meta: { className: "cell-center", width: 40 },
      },
      // Contact
      {
        header: "Contact",
        id: "contact_name",
        cell: ({ row }) => {
          const cc = row.original;
          const name =
            cc.contact_name ||
            (cc.contact && typeof cc.contact === "object"
              ? `${cc.contact.first_name || ""} ${cc.contact.last_name || ""}`.trim()
              : null) ||
            "—";
          return (
            <Typography variant="subtitle2" fontWeight={600}>
              {name}
            </Typography>
          );
        },
      },
      // Department
      {
        header: "Department",
        id: "department",
        cell: ({ row }) => {
          const dept = row.original.department_name;
          return (
            <Typography
              variant="body2"
              color={dept ? "text.primary" : "text.disabled"}
            >
              {dept || "—"}
            </Typography>
          );
        },
      },
      // Account
      {
        header: "Account",
        id: "account_name",
        cell: ({ row }) => (
          <Typography variant="body2">
            {row.original.account_name || "—"}
          </Typography>
        ),
      },
      // Status
      {
        header: "Status",
        id: "status",
        cell: ({ row }) => {
          const cc = row.original;
          if (cc.has_on_hold) {
            return (
              <Chip
                label="On Hold"
                size="small"
                color="warning"
                variant="filled"
              />
            );
          }
          const cfg =
            CONTACT_STATUS_CONFIG[cc.status] || CONTACT_STATUS_CONFIG.PENDING;
          return (
            <Chip
              label={cfg.label}
              size="small"
              color={cfg.color}
              variant="filled"
            />
          );
        },
      },
      // Actions
      {
        header: "",
        id: "actions",
        enableSorting: false,
        meta: { className: "cell-center" },
        cell: ({ row }) => {
          const cc = row.original;
          const isActing = !!actionInProgress && actionInProgress.id === cc.id;
          const isPaused = cc.has_on_hold;
          const isFinalContact = ["COMPLETED", "STOPPED"].includes(cc.status);

          // Non-TARGETED completed campaign → no actions
          if (isFinal && !isTargeted) return null;

          // TARGETED finished contact (COMPLETED or STOPPED) → no actions: the
          // chase is over. Re-chasing happens by re-enrolling the contact from
          // the Add Target modal, not from a per-row action here.
          if (isTargeted && isFinalContact) return null;

          // ON_HOLD (paused) → Resume + Stop
          if (isPaused) {
            return (
              <Stack direction="row" spacing={0.5} justifyContent="center">
                <Tooltip title="Resume sequence">
                  <span>
                    <IconButton
                      size="small"
                      color="success"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleResumeRow(cc);
                      }}
                      disabled={!!actionInProgress}
                    >
                      {isActing && actionInProgress?.type === "resume" ? (
                        <CircularProgress size={14} />
                      ) : (
                        <PlayCircleOutlined />
                      )}
                    </IconButton>
                  </span>
                </Tooltip>
                <Tooltip title="Stop contact">
                  <span>
                    <IconButton
                      size="small"
                      color="error"
                      onClick={(e) => {
                        e.stopPropagation();
                        requestStop(cc);
                      }}
                      disabled={!!actionInProgress}
                    >
                      {isActing && actionInProgress?.type === "stop" ? (
                        <CircularProgress size={14} />
                      ) : (
                        <StopOutlined />
                      )}
                    </IconButton>
                  </span>
                </Tooltip>
              </Stack>
            );
          }

          // IN_PROGRESS / PENDING → Pause + Stop
          return (
            <Stack direction="row" spacing={0.5} justifyContent="center">
              <Tooltip title="Pause sequence">
                <span>
                  <IconButton
                    size="small"
                    color="warning"
                    onClick={(e) => {
                      e.stopPropagation();
                      handlePauseRow(cc);
                    }}
                    disabled={!!actionInProgress}
                  >
                    {isActing && actionInProgress?.type === "pause" ? (
                      <CircularProgress size={14} />
                    ) : (
                      <PauseCircleOutlined />
                    )}
                  </IconButton>
                </span>
              </Tooltip>
              <Tooltip title="Stop contact">
                <span>
                  <IconButton
                    size="small"
                    color="error"
                    onClick={(e) => {
                      e.stopPropagation();
                      requestStop(cc);
                    }}
                    disabled={!!actionInProgress}
                  >
                    {isActing && actionInProgress?.type === "stop" ? (
                      <CircularProgress size={14} />
                    ) : (
                      <StopOutlined />
                    )}
                  </IconButton>
                </span>
              </Tooltip>
            </Stack>
          );
        },
      },
    ],
    [
      allSelected,
      someSelected,
      selectedRows,
      handleSelectAll,
      handleSelectRow,
      handlePauseRow,
      handleResumeRow,
      actionInProgress,
      isFinal,
    ],
  );

  // ==============================|| BULK ACTION BAR ||============================== //

  const bulkActionBar =
    selectedRows.size > 0 && !isFinal ? (
      <Stack
        direction="row"
        spacing={1}
        alignItems="center"
        sx={{
          px: 2,
          py: 1,
          mb: 1,
          bgcolor: "primary.lighter",
          borderRadius: 1,
        }}
      >
        <Typography variant="body2" fontWeight={500}>
          {selectedRows.size} selected
        </Typography>
        <Box sx={{ flex: 1 }} />
        <Button
          size="small"
          variant="outlined"
          color="warning"
          startIcon={<PauseCircleOutlined />}
          onClick={handleBulkPause}
          disabled={!!actionInProgress}
        >
          Pause
        </Button>
        <Button
          size="small"
          variant="outlined"
          color="success"
          startIcon={<PlayCircleOutlined />}
          onClick={handleBulkResume}
          disabled={!!actionInProgress}
        >
          Resume
        </Button>
        <Button
          size="small"
          variant="contained"
          color="error"
          startIcon={<DeleteOutlined />}
          onClick={handleBulkRemove}
          disabled={!!actionInProgress}
        >
          Remove
        </Button>
      </Stack>
    ) : null;

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      {bulkActionBar}

      {/* Action bar — status toggle + Add Target on one aligned row. Mirrors
          the list-view action cluster (views/campaigns/list.jsx): a
          right-aligned Stack row holding the filter control and the primary
          contained action. The binary toggle follows SignalsViewToggle
          (ToggleButtonGroup, exclusive, size="small", no-empty guard). Add
          Target is lifted out of the table here (showAddButton={false} below)
          so it shares this row instead of the table toolbar. */}
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="flex-end"
        spacing={1}
        sx={{ mb: 1.5 }}
      >
        <ToggleButtonGroup
          value={statusFilter}
          exclusive
          size="small"
          onChange={(_, value) => {
            if (value) setStatusFilter(value);
          }}
          aria-label="Chasing status filter"
        >
          <ToggleButton value="active" aria-label="Active">
            Active
          </ToggleButton>
          <ToggleButton value="all" aria-label="All">
            All
          </ToggleButton>
        </ToggleButtonGroup>

        {!isFinal && (
          <Button
            variant="contained"
            startIcon={<PlusOutlined />}
            onClick={() => setAddTargetOpen(true)}
          >
            Add Target
          </Button>
        )}
      </Stack>

      <ReusableTable
        data={filteredContacts}
        columns={columns}
        loading={campaignContactsLoading}
        error={campaignContactsError}
        totalCount={filteredContacts.length}
        onSearchChange={setSearch}
        sorting={sorting}
        onSortingChange={handleSortingChange}
        searchPlaceholder={`Search ${campaignContacts.length} targets...`}
        emptyMessage="No targets enrolled"
        emptyDescription={
          isFinal
            ? "This campaign has ended."
            : "Add contacts to this campaign."
        }
        enableImport={false}
        showAddButton={false}
      />

      <AddTargetToCampaignModal
        campaignId={campaignId}
        enrolledContactIds={enrolledContactIds}
        open={addTargetOpen}
        onClose={() => setAddTargetOpen(false)}
        onSuccess={mutateCampaignContacts}
      />

      {/* ── Confirm Stop Dialog ──
          Stop is irreversible from this view, so it is confirmed before firing.
          Follows the AlertCampaignDelete confirmation pattern (warning title,
          Cancel + destructive contained action). */}
      <Dialog
        open={Boolean(confirmStop)}
        onClose={() => setConfirmStop(null)}
        maxWidth="xs"
        fullWidth
        aria-labelledby="confirm-stop-title"
        aria-describedby="confirm-stop-description"
      >
        <DialogTitle id="confirm-stop-title">
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            <WarningFilled style={{ fontSize: 24, color: "#faad14" }} />
            <Typography variant="h5">Stop contact</Typography>
          </Box>
        </DialogTitle>
        <DialogContent>
          <DialogContentText id="confirm-stop-description">
            Are you sure you want to remove{" "}
            <Typography component="span" fontWeight={600} color="text.primary">
              {confirmStop?.contact_name || "this contact"}
              {confirmStop?.account_name ? ` — ${confirmStop.account_name}` : ""}
            </Typography>{" "}
            from the campaign?
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button color="secondary" onClick={() => setConfirmStop(null)}>
            Cancel
          </Button>
          <Button variant="contained" color="error" onClick={handleConfirmStop}>
            Stop
          </Button>
        </DialogActions>
      </Dialog>

      {/* ── Confirm Remove Dialog ──
      <Dialog
        open={Boolean(confirmRemove)}
        onClose={() => setConfirmRemove(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Remove from campaign?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Remove <strong>{confirmRemove?.label}</strong> from this campaign?
            Remaining planned activities will be cancelled. Completed activities
            are kept.
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button
            onClick={() => setConfirmRemove(null)}
            color="inherit"
            size="small"
          >
            Cancel
          </Button>
          <Button
            onClick={handleConfirmRemove}
            variant="contained"
            color="error"
            size="small"
          >
            Remove
          </Button>
        </DialogActions> */}
      {/* </Dialog> */}
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

TargetsTab.propTypes = {
  campaignId: PropTypes.string.isRequired,
  campaign: PropTypes.shape({
    status: PropTypes.string,
    campaign_type: PropTypes.string,
  }),
};
