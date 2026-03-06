// frontend/src/sections/campaigns/workspace/CampaignAccountsTab.jsx
/**
 * Campaign Accounts Tab — Enrolled accounts with Add/Remove + Contact targeting.
 *
 * Pattern: sections/territories/workspace/TerritoryAccountsTab.jsx
 * Uses ReusableTable with server-side pagination + search + sorting.
 * "Add Accounts" button is the native ReusableTable toolbar button (modalToggler).
 *
 * Backend serializer fields (CampaignAccountListSerializer):
 *   id, campaign, account (UUID), account_name, status, status_display,
 *   callback_date, activities_generated, no_answer_count, contacts_count
 */

"use client";

import PropTypes from "prop-types";
import { useMemo, useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";

// material-ui
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Collapse from "@mui/material/Collapse";
import Dialog from "@mui/material/Dialog";
import DialogTitle from "@mui/material/DialogTitle";
import DialogContent from "@mui/material/DialogContent";
import DialogActions from "@mui/material/DialogActions";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// project imports
import IconButton from "components/@extended/IconButton";
import ReusableTable from "components/table/Table";
import AsyncAccountSelect from "components/AsyncSelection/AsyncAccountSelect";

// hooks
import useLocalStorage from "hooks/useLocalStorage";
import { useAuth } from "hooks/useAuth";

// api
import {
  useGetCampaignAccounts,
  addAccountsToCampaign,
  removeAccountFromCampaign,
  toggleAccountContact,
} from "api/campaigns/campaigns";
import { useGetContacts } from "api/businessData/contacts";
import { api } from "utils/axiosClient";
import { tenantKey } from "api/_swr";

// utils
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// icons
import DeleteOutlined from "@ant-design/icons/DeleteOutlined";
import ArrowRightOutlined from "@ant-design/icons/ArrowRightOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";

// ==============================|| STATUS CONFIG ||============================== //

const CAMPAIGN_ACCOUNT_STATUS_CONFIG = {
  PENDING: { label: "Pending", color: "default" },
  IN_PROGRESS: { label: "In Progress", color: "info" },
  CALLBACK_PENDING: { label: "Callback Pending", color: "warning" },
  COMPLETED: { label: "Completed", color: "success" },
  STOPPED: { label: "Stopped", color: "error" },
};

const COLUMN_TO_BACKEND_FIELD = {
  account_name: "account__company_name",
  status: "status",
  contacts_count: "contacts_count",
  activities_generated: "activities_generated",
};

// ==============================|| CONTACT TARGETING DIALOG ||============================== //

function ContactTargetingDialog({ open, onClose, campaignAccount, onToggled }) {
  const [targetContactIds, setTargetContactIds] = useState(new Set());
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [togglingId, setTogglingId] = useState(null);

  // Load contacts for this account
  const { contacts, contactsLoading } = useGetContacts(
    open && campaignAccount
      ? { page: 1, pageSize: 100, filters: { account_id: campaignAccount.account } }
      : null,
  );

  // Load CampaignAccount detail to get current target_contacts
  useEffect(() => {
    if (!open || !campaignAccount) return;
    let cancelled = false;

    setLoadingDetail(true);
    api.get(`/campaigns/accounts/${campaignAccount.id}/`).then((result) => {
      if (cancelled) return;
      setLoadingDetail(false);
      if (result.success && result.data) {
        const data = result.data?.data || result.data;
        const ids = (data.target_contacts || []).map((c) => c.id);
        setTargetContactIds(new Set(ids));
      }
    });

    return () => { cancelled = true; };
  }, [open, campaignAccount]);

  const handleToggle = useCallback(
    async (contactId) => {
      if (togglingId) return;
      setTogglingId(contactId);

      try {
        const result = await toggleAccountContact(campaignAccount.id, contactId);
        if (result.success) {
          const action = result.data?.action;
          setTargetContactIds((prev) => {
            const next = new Set(prev);
            if (action === "removed") {
              next.delete(contactId);
            } else {
              next.add(contactId);
            }
            return next;
          });
          onToggled?.();
        } else {
          displayErrorSnackbar(result);
        }
      } catch (err) {
        displayErrorSnackbar(err);
      } finally {
        setTogglingId(null);
      }
    },
    [campaignAccount, togglingId, onToggled],
  );

  const loading = contactsLoading || loadingDetail;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        Target Contacts — {campaignAccount?.account_name || "Account"}
      </DialogTitle>
      <DialogContent dividers>
        {loading ? (
          <Stack alignItems="center" py={3}>
            <CircularProgress size={28} />
          </Stack>
        ) : contacts.length === 0 ? (
          <Typography color="text.secondary" py={2} textAlign="center">
            No contacts found for this account.
          </Typography>
        ) : (
          <>
            <Typography variant="caption" color="text.secondary" mb={1} display="block">
              Check contacts to include in this campaign. Unchecked contacts will be excluded.
            </Typography>
            <List dense>
              {contacts.map((contact) => {
                const isTarget = targetContactIds.has(contact.id);
                const isToggling = togglingId === contact.id;
                const fullName =
                  `${contact.first_name || ""} ${contact.last_name || ""}`.trim() || "—";

                return (
                  <ListItem key={contact.id} disablePadding>
                    <ListItemButton
                      onClick={() => handleToggle(contact.id)}
                      disabled={isToggling}
                      dense
                    >
                      <ListItemIcon sx={{ minWidth: 36 }}>
                        {isToggling ? (
                          <CircularProgress size={20} />
                        ) : (
                          <Checkbox
                            edge="start"
                            checked={isTarget}
                            tabIndex={-1}
                            disableRipple
                          />
                        )}
                      </ListItemIcon>
                      <ListItemText
                        primary={fullName}
                        secondary={
                          [contact.job_title, contact.email].filter(Boolean).join(" · ") || null
                        }
                      />
                    </ListItemButton>
                  </ListItem>
                );
              })}
            </List>
          </>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

ContactTargetingDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  campaignAccount: PropTypes.object,
  onToggled: PropTypes.func,
};

// ==============================|| CAMPAIGN ACCOUNTS TAB ||============================== //

export default function CampaignAccountsTab({ campaignId, campaign }) {
  const { tenantId } = useAuth();
  const router = useRouter();

  // ==============================|| STATE ||============================== //

  const [pageSize, setPageSize] = useLocalStorage(
    "campaignAccountsPageSize",
    25,
  );
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [sorting, setSorting] = useState([]);

  // Controls the AsyncAccountSelect panel — opened by ReusableTable's add button
  const [addOpen, setAddOpen] = useState(false);
  const [addingAccount, setAddingAccount] = useState(false);
  const [removingId, setRemovingId] = useState(null);

  // Contact targeting dialog
  const [contactTarget, setContactTarget] = useState(null);

  // ==============================|| DERIVED STATE ||============================== //

  const validPageSize = useMemo(() => {
    const size = Number(pageSize);
    return [10, 25, 50, 100].includes(size) ? size : 25;
  }, [pageSize]);

  const ordering = useMemo(() => {
    if (!sorting.length) return "";
    const sort = sorting[0];
    const backendField = COLUMN_TO_BACKEND_FIELD[sort.id] || sort.id;
    return sort.desc ? `-${backendField}` : backendField;
  }, [sorting]);

  const isFinalStatus =
    campaign?.status === "COMPLETED" || campaign?.status === "CANCELLED";

  // ==============================|| DATA ||============================== //

  const {
    accounts,
    accountsCount,
    accountsLoading,
    accountsError,
    mutateAccounts,
  } = useGetCampaignAccounts(campaignId, {
    page,
    pageSize: validPageSize,
  });

  const swrKey = tenantKey(
    `/campaigns/accounts/by-campaign/?campaign_id=${campaignId}&page=${page}&page_size=${validPageSize}`,
    tenantId,
  );

  // Exclude already-enrolled accounts from the selector
  const enrolledAccountIds = useMemo(
    () => accounts.map((a) => a.account),
    [accounts],
  );

  // ==============================|| HANDLERS ||============================== //

  const handlePaginationChange = useCallback(
    ({ page: newPage, pageSize: newPageSize }) => {
      setPage(newPage);
      if (newPageSize !== validPageSize) setPageSize(newPageSize);
    },
    [validPageSize, setPageSize],
  );

  const handleSearchChange = useCallback((value) => {
    setSearch(value);
    setPage(1);
  }, []);

  const handleSortingChange = useCallback((updaterOrValue) => {
    setSorting((prev) =>
      typeof updaterOrValue === "function"
        ? updaterOrValue(prev)
        : updaterOrValue,
    );
  }, []);

  const handleRowClick = useCallback(
    (row) => {
      if (row?.account) router.push(`/accounts/${row.account}`);
    },
    [router],
  );

  /**
   * Called by ReusableTable's native "Add" button (modalToggler).
   * Toggles the AsyncAccountSelect panel.
   */
  const handleOpenAddPanel = useCallback(() => {
    setAddOpen((prev) => !prev);
  }, []);

  /**
   * AsyncAccountSelect onChange fires inside MUI Autocomplete render cycle.
   * Defer setAddingAccount(true) to avoid the "setState during render" warning.
   */
  const handleAddAccount = useCallback(
    (event, account) => {
      if (!account?.id) return;
      // Defer entire handler outside Autocomplete's render cycle
      setTimeout(async () => {
        setAddingAccount(true);
        try {
          const result = await addAccountsToCampaign(campaignId, [account.id]);
          if (result.success) {
            displaySuccessSnackbar(
              `${account.company_name || "Account"} added to campaign`,
            );
            setPage(1);
            mutateAccounts();
          } else {
            displayErrorSnackbar(result);
          }
        } catch (err) {
          displayErrorSnackbar(err);
        } finally {
          setAddingAccount(false);
        }
      }, 0);
    },
    [campaignId, mutateAccounts],
  );

  const handleRemoveAccount = useCallback(
    async (campaignAccount) => {
      const name = campaignAccount.account_name || "this account";
      if (!window.confirm(`Remove ${name} from campaign?`)) return;
      setRemovingId(campaignAccount.id);
      try {
        const result = await removeAccountFromCampaign(
          campaignAccount.id,
          campaignId,
        );
        if (result.success) {
          displaySuccessSnackbar(`${name} removed from campaign`);
          mutateAccounts();
        } else {
          displayErrorSnackbar(result);
        }
      } catch (err) {
        displayErrorSnackbar(err);
      } finally {
        setRemovingId(null);
      }
    },
    [campaignId, mutateAccounts],
  );

  const handleOpenContactDialog = useCallback((ca, e) => {
    if (e) e.stopPropagation();
    setContactTarget(ca);
  }, []);

  const handleContactToggled = useCallback(() => {
    mutateAccounts();
  }, [mutateAccounts]);

  // ==============================|| COLUMNS ||============================== //

  const columns = useMemo(
    () => [
      // Company Name
      {
        header: "Company",
        id: "account_name",
        accessorKey: "account_name",
        cell: ({ getValue }) => (
          <Typography variant="subtitle2" fontWeight={600}>
            {getValue() || "—"}
          </Typography>
        ),
      },
      // Enrollment Status
      {
        header: "Status",
        id: "status",
        accessorKey: "status",
        cell: ({ row }) => {
          const cfg =
            CAMPAIGN_ACCOUNT_STATUS_CONFIG[row.original.status] ||
            CAMPAIGN_ACCOUNT_STATUS_CONFIG.PENDING;
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
      // Activities generated
      {
        header: "Activities",
        id: "activities_generated",
        accessorKey: "activities_generated",
        enableSorting: false,
        cell: ({ getValue }) => (
          <Typography variant="body2">
            {getValue() ? "Generated" : "Pending"}
          </Typography>
        ),
      },
      // Contacts count — clickable to open targeting dialog
      {
        header: "Contacts",
        id: "contacts_count",
        accessorKey: "contacts_count",
        enableSorting: false,
        cell: ({ row }) => {
          const ca = row.original;
          const count = ca.contacts_count || 0;
          return (
            <Tooltip title="Manage target contacts">
              <Button
                size="small"
                variant="text"
                startIcon={<TeamOutlined />}
                onClick={(e) => handleOpenContactDialog(ca, e)}
                sx={{ textTransform: "none", minWidth: 0 }}
              >
                {count}
              </Button>
            </Tooltip>
          );
        },
      },
      // Actions
      {
        header: "",
        id: "actions",
        meta: { className: "cell-center" },
        enableSorting: false,
        cell: ({ row }) => {
          const ca = row.original;
          const canRemove = ca.status === "PENDING" && !isFinalStatus;
          const isRemoving = removingId === ca.id;

          return (
            <Stack direction="row" justifyContent="center" spacing={0.5}>
              <Tooltip title="Open Account">
                <IconButton
                  size="small"
                  color="primary"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRowClick(ca);
                  }}
                >
                  <ArrowRightOutlined />
                </IconButton>
              </Tooltip>

              {canRemove ? (
                <Tooltip title="Remove from campaign">
                  <IconButton
                    size="small"
                    color="error"
                    disabled={isRemoving}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRemoveAccount(ca);
                    }}
                  >
                    {isRemoving ? (
                      <CircularProgress size={14} color="error" />
                    ) : (
                      <DeleteOutlined />
                    )}
                  </IconButton>
                </Tooltip>
              ) : !isFinalStatus ? (
                <Tooltip title="Only pending accounts can be removed">
                  <span>
                    <IconButton size="small" disabled>
                      <DeleteOutlined />
                    </IconButton>
                  </span>
                </Tooltip>
              ) : null}
            </Stack>
          );
        },
      },
    ],
    [isFinalStatus, removingId, handleRowClick, handleRemoveAccount, handleOpenContactDialog],
  );

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      {/* AsyncAccountSelect panel — toggled by ReusableTable's add button */}
      <Collapse in={addOpen}>
        <Box
          sx={{
            mb: 2,
            p: 2,
            border: "1px dashed",
            borderColor: "divider",
            borderRadius: 1.5,
          }}
        >
          <AsyncAccountSelect
            value={null}
            onChange={handleAddAccount}
            label=""
            placeholder="Search accounts to add..."
            excludeIds={enrolledAccountIds}
            disabled={addingAccount}
          />
          {addingAccount && (
            <Stack
              direction="row"
              spacing={1}
              alignItems="center"
              sx={{ mt: 1 }}
            >
              <CircularProgress size={16} />
              <Typography variant="caption" color="text.secondary">
                Adding account...
              </Typography>
            </Stack>
          )}
        </Box>
      </Collapse>

      <ReusableTable
        data={accounts}
        columns={columns}
        loading={accountsLoading}
        error={accountsError}
        swrKey={swrKey}
        totalCount={accountsCount}
        currentPage={page}
        onPaginationChange={handlePaginationChange}
        onSearchChange={handleSearchChange}
        initialPageSize={validPageSize}
        sorting={sorting}
        onSortingChange={handleSortingChange}
        onRowClick={handleRowClick}
        searchPlaceholder={`Search ${accountsCount || 0} accounts...`}
        emptyMessage="No accounts in this campaign"
        emptyDescription={
          isFinalStatus
            ? "This campaign has ended."
            : 'Click "Add Accounts" to enroll accounts.'
        }
        // Native ReusableTable add button → opens AsyncAccountSelect panel
        modalToggler={isFinalStatus ? null : handleOpenAddPanel}
        addButtonLabel="Add Accounts"
        addButtonTooltip="Enroll accounts in this campaign"
        showAddButton={!isFinalStatus}
        enableImport={false}
      />

      {/* Contact Targeting Dialog */}
      <ContactTargetingDialog
        open={!!contactTarget}
        onClose={() => setContactTarget(null)}
        campaignAccount={contactTarget}
        onToggled={handleContactToggled}
      />
    </Box>
  );
}

CampaignAccountsTab.propTypes = {
  campaignId: PropTypes.string,
  campaign: PropTypes.object,
};
