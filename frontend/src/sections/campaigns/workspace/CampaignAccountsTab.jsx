// frontend/src/sections/campaigns/workspace/CampaignAccountsTab.jsx
/**
 * Campaign Accounts Tab — Table of targeted accounts.
 *
 * MVP: Simple MUI Table with inline mock data.
 * Future: ReusableTable with real API + pagination.
 *
 * Pattern: Simple table like BulkImportReport, not full ReusableTable (overkill for mock).
 */

'use client';

import PropTypes from 'prop-types';
import { useMemo } from 'react';

// material-ui
import { useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Stack from '@mui/material/Stack';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';

// icons
import ArrowRightOutlined from '@ant-design/icons/ArrowRightOutlined';

// ==============================|| MOCK DATA ||============================== //

const MOCK_ACCOUNTS = [
  { id: 'acc-1', company_name: 'Acme Corp', type: 'PROSPECT', campaign_status: 'IN_PROGRESS', activities_count: 4, activities_completed: 1 },
  { id: 'acc-2', company_name: 'TechFlow GmbH', type: 'PROSPECT', campaign_status: 'PENDING', activities_count: 3, activities_completed: 0 },
  { id: 'acc-3', company_name: 'DataSync AG', type: 'ENTERPRISE', campaign_status: 'COMPLETED', activities_count: 3, activities_completed: 3 },
  { id: 'acc-4', company_name: 'CloudNine SaaS', type: 'SMB', campaign_status: 'IN_PROGRESS', activities_count: 4, activities_completed: 2 },
  { id: 'acc-5', company_name: 'FinServe Ltd', type: 'ENTERPRISE', campaign_status: 'PENDING', activities_count: 3, activities_completed: 0 }
];

// ==============================|| STATUS CONFIG ||============================== //

const CAMPAIGN_STATUS_CONFIG = {
  PENDING: { label: 'Pending', color: 'default' },
  IN_PROGRESS: { label: 'In Progress', color: 'info' },
  COMPLETED: { label: 'Completed', color: 'success' },
  SKIPPED: { label: 'Skipped', color: 'warning' }
};

const TYPE_COLORS = {
  PROSPECT: 'primary',
  ENTERPRISE: 'secondary',
  SMB: 'default',
  PARTNER: 'info'
};

// ==============================|| CAMPAIGN ACCOUNTS TAB ||============================== //

export default function CampaignAccountsTab({ campaignId, campaign }) {
  const theme = useTheme();

  // TODO: Replace with real API hook when backend is ready
  const accounts = MOCK_ACCOUNTS;

  // ==============================|| EMPTY STATE ||============================== //

  if (accounts.length === 0) {
    return (
      <Box sx={{ py: 6, textAlign: 'center' }}>
        <Typography variant="h5" color="text.secondary">
          No accounts in this campaign
        </Typography>
        <Typography variant="body2" color="text.disabled" sx={{ mt: 1 }}>
          Accounts will appear here once the campaign is started.
        </Typography>
      </Box>
    );
  }

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      {/* Summary */}
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {accounts.length} account{accounts.length !== 1 ? 's' : ''} targeted in this campaign
      </Typography>

      {/* Table */}
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Company</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Activities</TableCell>
              <TableCell>Progress</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {accounts.map((account) => {
              const statusConfig = CAMPAIGN_STATUS_CONFIG[account.campaign_status] || CAMPAIGN_STATUS_CONFIG.PENDING;
              const progress = account.activities_count > 0
                ? Math.round((account.activities_completed / account.activities_count) * 100)
                : 0;

              return (
                <TableRow key={account.id} hover>
                  {/* Company Name */}
                  <TableCell>
                    <Typography variant="subtitle2">
                      {account.company_name}
                    </Typography>
                  </TableCell>

                  {/* Type */}
                  <TableCell>
                    <Chip
                      label={account.type}
                      size="small"
                      color={TYPE_COLORS[account.type] || 'default'}
                      variant="outlined"
                    />
                  </TableCell>

                  {/* Campaign Status */}
                  <TableCell>
                    <Chip
                      label={statusConfig.label}
                      size="small"
                      color={statusConfig.color}
                      variant="filled"
                    />
                  </TableCell>

                  {/* Activities Count */}
                  <TableCell>
                    <Typography variant="body2">
                      {account.activities_completed}/{account.activities_count}
                    </Typography>
                  </TableCell>

                  {/* Progress Bar */}
                  <TableCell sx={{ minWidth: 120 }}>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <LinearProgress
                        variant="determinate"
                        value={progress}
                        color={progress >= 100 ? 'success' : 'primary'}
                        sx={{ flexGrow: 1, height: 6, borderRadius: 3 }}
                      />
                      <Typography variant="caption" color="text.secondary" sx={{ minWidth: 32 }}>
                        {progress}%
                      </Typography>
                    </Stack>
                  </TableCell>

                  {/* Actions */}
                  <TableCell align="center">
                    <Tooltip title="Open Account">
                      <IconButton
                        size="small"
                        color="primary"
                        onClick={() => console.log('TODO: Navigate to account', account.id)}
                      >
                        <ArrowRightOutlined style={{ fontSize: 16 }} />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

CampaignAccountsTab.propTypes = {
  campaignId: PropTypes.string,
  campaign: PropTypes.object
};