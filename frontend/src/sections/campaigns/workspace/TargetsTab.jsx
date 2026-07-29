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
import StopOutlined from "@ant-design/icons/StopOutlined";
import WarningFilled from "@ant-design/icons/WarningFilled";

// Project
import ReusableTable from "components/table/Table";
import AddTargetToCampaignModal from "./AddTargetToCampaignModal";
import {
  useGetCampaignContacts,
  pauseTarget,
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

// Default row order (product decision): running sequences first, then targets
// enrolled-but-never-started (a potential oversight — kept visible high), then
// the deliberate waiting states, then the two terminals at the bottom (succeeded
// before abandoned). Used only as the DEFAULT order — a user column sort wins.
const STATUS_ORDER = [
  "IN_PROGRESS",
  "PENDING",
  "CALLBACK_PENDING",
  "ON_HOLD",
  "COMPLETED",
  "STOPPED",
];

// Rank of a status in STATUS_ORDER; an unknown status (enum drift) sorts last
// rather than throwing.
const statusRank = (status) => {
  const i = STATUS_ORDER.indexOf(status);
  return i === -1 ? STATUS_ORDER.length : i;
};

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
  const [actionInProgress, setActionInProgress] = useState(null);
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

  // ==============================|| STATUS + SEARCH FILTER + SORT ||============================== //

  const filteredContacts = useMemo(() => {
    const q = search.trim().toLowerCase();
    const rows = campaignContacts.filter((cc) => {
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

    // The table uses manualSorting, so it renders rows in this array's order.
    // Default: status priority (STATUS_ORDER), then contact name for a stable,
    // predictable tiebreak. An active column-header sort takes over instead.
    const byName = (a, b) =>
      (a.contact_name || "").localeCompare(b.contact_name || "");

    const active = sorting?.[0];
    if (active) {
      const valueOf = (cc) => {
        switch (active.id) {
          case "status":
            return statusRank(cc.status);
          case "contact_name":
            return (cc.contact_name || "").toLowerCase();
          case "department":
            return (cc.department_name || "").toLowerCase();
          case "account_name":
            return (cc.account_name || "").toLowerCase();
          default:
            return "";
        }
      };
      rows.sort((a, b) => {
        const av = valueOf(a);
        const bv = valueOf(b);
        const cmp = av < bv ? -1 : av > bv ? 1 : byName(a, b);
        return active.desc ? -cmp : cmp;
      });
    } else {
      rows.sort(
        (a, b) => statusRank(a.status) - statusRank(b.status) || byName(a, b),
      );
    }

    return rows;
  }, [campaignContacts, search, statusFilter, sorting]);

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

  // ==============================|| COLUMNS ||============================== //

  const columns = useMemo(
    () => [
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
      handlePauseRow,
      handleResumeRow,
      actionInProgress,
      isFinal,
    ],
  );

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
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
        modalToggler={() => setAddTargetOpen(true)}
        addButtonLabel="Add Target"
        enableImport={false}
        showAddButton={!isFinal}
        // Chasing-status toggle rendered in the table toolbar, left of Add
        // Target. Binary toggle follows SignalsViewToggle (ToggleButtonGroup,
        // exclusive, size="small", no-empty guard).
        toolbarActions={
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
        }
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
