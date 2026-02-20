// frontend/src/sections/campaigns/workspace/CampaignActivitiesTab.jsx
/**
 * Campaign Activities Tab — Table of campaign activities.
 *
 * MVP: Simple MUI Table with inline mock data.
 * Future: ReusableTable with real API + pagination.
 */

'use client';

import PropTypes from 'prop-types';

// material-ui
import { useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
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
import PhoneOutlined from '@ant-design/icons/PhoneOutlined';
import MailOutlined from '@ant-design/icons/MailOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import CheckSquareOutlined from '@ant-design/icons/CheckSquareOutlined';

// ==============================|| MOCK DATA ||============================== //

const MOCK_ACTIVITIES = [
  { id: 'act-1', title: 'Initial Call — Acme Corp', activity_type: 'CALL', status: 'PLANNED', account_name: 'Acme Corp', contact_name: 'John Smith', due_date: '2026-02-21' },
  { id: 'act-2', title: 'Follow-up Email — Acme Corp', activity_type: 'EMAIL', status: 'PLANNED', account_name: 'Acme Corp', contact_name: 'John Smith', due_date: '2026-02-24' },
  { id: 'act-3', title: 'Intro Call — TechFlow', activity_type: 'CALL', status: 'IN_PROGRESS', account_name: 'TechFlow GmbH', contact_name: 'Maria Weber', due_date: '2026-02-22' },
  { id: 'act-4', title: 'Discovery Meeting — DataSync', activity_type: 'MEETING', status: 'COMPLETED', account_name: 'DataSync AG', contact_name: 'Hans Mueller', due_date: '2026-02-10' },
  { id: 'act-5', title: 'Send Proposal — CloudNine', activity_type: 'TASK', status: 'PLANNED', account_name: 'CloudNine SaaS', contact_name: 'Sophie Laurent', due_date: '2026-02-25' },
  { id: 'act-6', title: 'Follow-up Call — TechFlow', activity_type: 'CALL', status: 'CANCELLED', account_name: 'TechFlow GmbH', contact_name: 'Maria Weber', due_date: '2026-02-15' }
];

// ==============================|| TYPE CONFIG ||============================== //

const TYPE_CONFIG = {
  CALL: { Icon: PhoneOutlined, color: 'info' },
  EMAIL: { Icon: MailOutlined, color: 'warning' },
  MEETING: { Icon: TeamOutlined, color: 'success' },
  TASK: { Icon: CheckSquareOutlined, color: 'secondary' }
};

const STATUS_CONFIG = {
  PLANNED: { label: 'Planned', color: 'default' },
  IN_PROGRESS: { label: 'In Progress', color: 'info' },
  COMPLETED: { label: 'Completed', color: 'success' },
  CANCELLED: { label: 'Cancelled', color: 'error' }
};

// ==============================|| CAMPAIGN ACTIVITIES TAB ||============================== //

export default function CampaignActivitiesTab({ campaignId, campaign }) {
  const theme = useTheme();

  // TODO: Replace with real API hook when backend is ready
  const activities = MOCK_ACTIVITIES;

  // ==============================|| HELPERS ||============================== //

  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    const d = new Date(dateStr);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const isOverdue = (dateStr, status) => {
    if (!dateStr || status === 'COMPLETED' || status === 'CANCELLED') return false;
    return new Date(dateStr) < new Date();
  };

  // ==============================|| EMPTY STATE ||============================== //

  if (activities.length === 0) {
    return (
      <Box sx={{ py: 6, textAlign: 'center' }}>
        <Typography variant="h5" color="text.secondary">
          No activities in this campaign
        </Typography>
        <Typography variant="body2" color="text.disabled" sx={{ mt: 1 }}>
          Activities will be generated when the campaign starts.
        </Typography>
      </Box>
    );
  }

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      {/* Summary */}
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {activities.length} activit{activities.length !== 1 ? 'ies' : 'y'} in this campaign
      </Typography>

      {/* Table */}
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Title</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Account</TableCell>
              <TableCell>Contact</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Due Date</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {activities.map((activity) => {
              const typeConfig = TYPE_CONFIG[activity.activity_type] || TYPE_CONFIG.TASK;
              const statusConfig = STATUS_CONFIG[activity.status] || STATUS_CONFIG.PLANNED;
              const TypeIcon = typeConfig.Icon;
              const overdue = isOverdue(activity.due_date, activity.status);

              return (
                <TableRow key={activity.id} hover>
                  {/* Title */}
                  <TableCell>
                    <Typography variant="subtitle2" noWrap sx={{ maxWidth: 240 }}>
                      {activity.title}
                    </Typography>
                  </TableCell>

                  {/* Type */}
                  <TableCell>
                    <Chip
                      icon={<TypeIcon style={{ fontSize: 14 }} />}
                      label={activity.activity_type}
                      size="small"
                      color={typeConfig.color}
                      variant="outlined"
                    />
                  </TableCell>

                  {/* Account */}
                  <TableCell>
                    <Typography variant="body2">
                      {activity.account_name || '—'}
                    </Typography>
                  </TableCell>

                  {/* Contact */}
                  <TableCell>
                    <Typography variant="body2">
                      {activity.contact_name || '—'}
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

                  {/* Due Date */}
                  <TableCell>
                    <Typography
                      variant="body2"
                      color={overdue ? 'error.main' : 'text.primary'}
                      fontWeight={overdue ? 600 : 400}
                    >
                      {formatDate(activity.due_date)}
                    </Typography>
                  </TableCell>

                  {/* Actions */}
                  <TableCell align="center">
                    <Tooltip title="Open Activity">
                      <IconButton
                        size="small"
                        color="primary"
                        onClick={() => console.log('TODO: Navigate to activity', activity.id)}
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

CampaignActivitiesTab.propTypes = {
  campaignId: PropTypes.string,
  campaign: PropTypes.object
};