// frontend/src/sections/campaigns/workspace/CampaignAccountsTab.jsx
/**
 * Campaign Accounts Tab — Table of enrolled accounts with Add/Remove.
 *
 * Real API: useGetCampaignAccounts, addAccountsToCampaign, removeAccountFromCampaign.
 * Backend serializer: CampaignAccountListSerializer fields:
 *   id, campaign, account (UUID), account_name, status, status_display,
 *   callback_date, activities_generated, no_answer_count, contacts_count,
 *   created_at, updated_at
 *
 * Pattern: Simple MUI Table (not full ReusableTable).
 */

"use client";

import PropTypes from "prop-types";
import { useState, useMemo } from "react";

// material-ui
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Collapse from "@mui/material/Collapse";
import IconButton from "@mui/material/IconButton";
import LinearProgress from "@mui/material/LinearProgress";
import Skeleton from "@mui/material/Skeleton";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// project imports
import AsyncAccountSelect from "components/AsyncSelection/AsyncAccountSelect";

// api
import {
  useGetCampaignAccounts,
  addAccountsToCampaign,
  removeAccountFromCampaign,
} from "api/campaigns/campaigns";

// utils
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// icons
import PlusOutlined from "@ant-design/icons/PlusOutlined";
import DeleteOutlined from "@ant-design/icons/DeleteOutlined";
import ArrowRightOutlined from "@ant-design/icons/ArrowRightOutlined";

// next
import { useRouter } from "next/navigation";

// ==============================|| STATUS CONFIG ||============================== //

const CAMPAIGN_ACCOUNT_STATUS_CONFIG = {
  PENDING: { label: "Pending", color: "default" },
  IN_PROGRESS: { label: "In Progress", color: "info" },
  CALLBACK_PENDING: { label: "Callback Pending", color: "warning" },
  COMPLETED: { label: "Completed", color: "success" },
  STOPPED: { label: "Stopped", color: "error" },
};

// ==============================|| LOADING SKELETON ||============================== //

function AccountsTableSkeleton() {
  return (
    <Stack spacing={1}>
      {[1, 2, 3, 4].map((i) => (
        <Skeleton
          key={i}
          variant="rectangular"
          height={48}
          sx={{ borderRadius: 1 }}
        />
      ))}
    </Stack>
  );
}

// ==============================|| CAMPAIGN ACCOUNTS TAB ||============================== //

export default function CampaignAccountsTab({ campaignId, campaign }) {
  const theme = useTheme();
  const router = useRouter();

  // ==============================|| STATE ||============================== //

  const [addOpen, setAddOpen] = useState(false);
  const [addingAccount, setAddingAccount] = useState(false);
  const [removingId, setRemovingId] = useState(null);

  // ==============================|| DATA ||============================== //

  const {
    accounts,
    accountsCount,
    accountsLoading,
    accountsError,
    mutateAccounts,
  } = useGetCampaignAccounts(campaignId);

  // Exclude already-enrolled account IDs from the add selector
  const enrolledAccountIds = useMemo(
    () => accounts.map((a) => a.account),
    [accounts],
  );

  // Campaign is in a final state — disable add/remove
  const isFinalStatus =
    campaign?.status === "COMPLETED" || campaign?.status === "CANCELLED";

  // ==============================|| HANDLERS ||============================== //

  const handleAddAccount = async (event, account) => {
    if (!account?.id) return;
    setAddingAccount(true);
    try {
      const result = await addAccountsToCampaign(campaignId, [account.id]);
      if (result.success) {
        displaySuccessSnackbar(`${account.company_name} added to campaign`);
        mutateAccounts();
      } else {
        displayErrorSnackbar(result.error || "Failed to add account");
      }
    } catch (err) {
      displayErrorSnackbar("An error occurred");
    } finally {
      setAddingAccount(false);
    }
  };

  const handleRemoveAccount = async (campaignAccount) => {
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
        displayErrorSnackbar(result.error || "Failed to remove account");
      }
    } catch (err) {
      displayErrorSnackbar("An error occurred");
    } finally {
      setRemovingId(null);
    }
  };

  const handleNavigateAccount = (accountId) => {
    if (accountId) {
      router.push(`/accounts/${accountId}`);
    }
  };

  // ==============================|| LOADING STATE ||============================== //

  if (accountsLoading) {
    return (
      <Box>
        <Skeleton variant="text" width={200} height={24} sx={{ mb: 2 }} />
        <AccountsTableSkeleton />
      </Box>
    );
  }

  // ==============================|| ERROR STATE ||============================== //

  if (accountsError) {
    return (
      <Box sx={{ py: 6, textAlign: "center" }}>
        <Typography variant="h5" color="error">
          Failed to load accounts
        </Typography>
        <Typography variant="body2" color="text.disabled" sx={{ mt: 1 }}>
          Please try refreshing the page.
        </Typography>
      </Box>
    );
  }

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      {/* Header: Count + Add button */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ mb: 2 }}
      >
        <Typography variant="body2" color="text.secondary">
          {accounts.length} account{accounts.length !== 1 ? "s" : ""} in this
          campaign
        </Typography>
        {!isFinalStatus && (
          <Button
            variant="outlined"
            size="small"
            startIcon={<PlusOutlined />}
            onClick={() => setAddOpen((prev) => !prev)}
          >
            {addOpen ? "Cancel" : "Add Accounts"}
          </Button>
        )}
      </Stack>

      {/* Add accounts section (collapsible) */}
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

      {/* Empty state */}
      {accounts.length === 0 ? (
        <Box sx={{ py: 6, textAlign: "center" }}>
          <Typography variant="h5" color="text.secondary">
            No accounts in this campaign
          </Typography>
          <Typography variant="body2" color="text.disabled" sx={{ mt: 1 }}>
            {isFinalStatus
              ? "This campaign has ended."
              : 'Use the "Add Accounts" button above to enroll accounts.'}
          </Typography>
        </Box>
      ) : (
        /* Table */
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Company</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Activities</TableCell>
                <TableCell>Contacts</TableCell>
                <TableCell align="center">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {accounts.map((ca) => {
                const statusConfig =
                  CAMPAIGN_ACCOUNT_STATUS_CONFIG[ca.status] ||
                  CAMPAIGN_ACCOUNT_STATUS_CONFIG.PENDING;
                const canRemove = ca.status === "PENDING" && !isFinalStatus;
                const isRemoving = removingId === ca.id;

                return (
                  <TableRow key={ca.id} hover>
                    {/* Company Name */}
                    <TableCell>
                      <Typography variant="subtitle2">
                        {ca.account_name || "—"}
                      </Typography>
                    </TableCell>

                    {/* Status */}
                    <TableCell>
                      <Chip
                        label={statusConfig.label}
                        size="small"
                        color={statusConfig.color}
                        variant="filled"
                      />
                    </TableCell>

                    {/* Activities generated */}
                    <TableCell>
                      <Typography variant="body2">
                        {ca.activities_generated ? "Yes" : "No"}
                      </Typography>
                    </TableCell>

                    {/* Contacts count */}
                    <TableCell>
                      <Typography variant="body2">
                        {ca.contacts_count || 0}
                      </Typography>
                    </TableCell>

                    {/* Actions: Navigate + Remove */}
                    <TableCell align="center">
                      <Stack
                        direction="row"
                        justifyContent="center"
                        spacing={0.5}
                      >
                        <Tooltip title="Open Account">
                          <IconButton
                            size="small"
                            color="primary"
                            onClick={() => handleNavigateAccount(ca.account)}
                          >
                            <ArrowRightOutlined style={{ fontSize: 16 }} />
                          </IconButton>
                        </Tooltip>

                        {canRemove ? (
                          <Tooltip title="Remove from campaign">
                            <IconButton
                              size="small"
                              color="error"
                              onClick={() => handleRemoveAccount(ca)}
                              disabled={isRemoving}
                            >
                              {isRemoving ? (
                                <CircularProgress size={14} color="error" />
                              ) : (
                                <DeleteOutlined style={{ fontSize: 16 }} />
                              )}
                            </IconButton>
                          </Tooltip>
                        ) : !isFinalStatus ? (
                          <Tooltip title="Only pending accounts can be removed">
                            <span>
                              <IconButton size="small" disabled>
                                <DeleteOutlined style={{ fontSize: 16 }} />
                              </IconButton>
                            </span>
                          </Tooltip>
                        ) : null}
                      </Stack>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}

CampaignAccountsTab.propTypes = {
  campaignId: PropTypes.string,
  campaign: PropTypes.object,
};
