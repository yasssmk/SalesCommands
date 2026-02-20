// frontend/src/sections/campaigns/workspace/CampaignMembersTab.jsx
/**
 * Campaign Members Tab — Members grouped by role.
 *
 * MVP: Mock data, "Add Member" button inopérant.
 * Future: Real API + add/remove members.
 *
 * Pattern: Simple cards grouped by role (Owner, Executor, Observer).
 */

'use client';

import PropTypes from 'prop-types';

// material-ui
import { alpha, useTheme } from '@mui/material/styles';
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// api
import { MEMBER_ROLE_LABELS } from 'api/campaigns/campaigns';

// icons
import PlusOutlined from '@ant-design/icons/PlusOutlined';
import CrownOutlined from '@ant-design/icons/CrownOutlined';
import UserOutlined from '@ant-design/icons/UserOutlined';
import EyeOutlined from '@ant-design/icons/EyeOutlined';

// ==============================|| MOCK DATA ||============================== //

const MOCK_MEMBERS = [
  { id: 'mem-1', user: { id: 'user-1', first_name: 'John', last_name: 'Doe', email: 'john@example.com' }, role: 'OWNER', is_primary_owner: true },
  { id: 'mem-2', user: { id: 'user-2', first_name: 'Jane', last_name: 'Smith', email: 'jane@example.com' }, role: 'EXECUTOR', is_primary_owner: false },
  { id: 'mem-3', user: { id: 'user-3', first_name: 'Bob', last_name: 'Wilson', email: 'bob@example.com' }, role: 'EXECUTOR', is_primary_owner: false },
  { id: 'mem-4', user: { id: 'user-4', first_name: 'Alice', last_name: 'Martin', email: 'alice@example.com' }, role: 'OBSERVER', is_primary_owner: false }
];

// ==============================|| ROLE CONFIG ||============================== //

const ROLE_CONFIG = {
  OWNER: { Icon: CrownOutlined, color: 'warning', avatarBg: 'warning.main' },
  EXECUTOR: { Icon: UserOutlined, color: 'primary', avatarBg: 'primary.main' },
  OBSERVER: { Icon: EyeOutlined, color: 'default', avatarBg: 'grey.500' }
};

const ROLE_ORDER = ['OWNER', 'EXECUTOR', 'OBSERVER'];

// ==============================|| MEMBER CARD ||============================== //

function MemberCard({ member }) {
  const theme = useTheme();
  const config = ROLE_CONFIG[member.role] || ROLE_CONFIG.OBSERVER;
  const user = member.user || {};
  const fullName = `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.email || 'Unknown';
  const initials = `${(user.first_name || '')[0] || ''}${(user.last_name || '')[0] || ''}`.toUpperCase() || '?';

  return (
    <Box
      sx={{
        p: 2,
        borderRadius: 1.5,
        border: '1px solid',
        borderColor: 'grey.200',
        bgcolor: 'background.paper',
        transition: 'all 0.2s ease',
        '&:hover': {
          borderColor: 'grey.300',
          bgcolor: 'grey.50'
        }
      }}
    >
      <Stack direction="row" spacing={2} alignItems="center">
        {/* Avatar */}
        <Avatar
          sx={{
            width: 40,
            height: 40,
            bgcolor: config.avatarBg,
            fontSize: '0.875rem',
            fontWeight: 600
          }}
        >
          {initials}
        </Avatar>

        {/* Info */}
        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="subtitle2" noWrap>
              {fullName}
            </Typography>
            {member.is_primary_owner && (
              <Chip label="Primary" size="small" color="warning" variant="outlined" sx={{ height: 20, fontSize: '0.675rem' }} />
            )}
          </Stack>
          <Typography variant="caption" color="text.secondary" noWrap>
            {user.email || '—'}
          </Typography>
        </Box>

        {/* Role Badge */}
        <Chip
          label={MEMBER_ROLE_LABELS[member.role] || member.role}
          size="small"
          color={config.color}
          variant="outlined"
        />
      </Stack>
    </Box>
  );
}

MemberCard.propTypes = {
  member: PropTypes.object.isRequired
};

// ==============================|| ROLE GROUP ||============================== //

function RoleGroup({ role, members }) {
  const theme = useTheme();
  const config = ROLE_CONFIG[role] || ROLE_CONFIG.OBSERVER;
  const RoleIcon = config.Icon;

  if (members.length === 0) return null;

  return (
    <Box>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
        <RoleIcon style={{ fontSize: 16, color: theme.palette.text.secondary }} />
        <Typography
          variant="subtitle2"
          color="text.secondary"
          sx={{ textTransform: 'uppercase', fontSize: '0.75rem', fontWeight: 600, letterSpacing: '0.5px' }}
        >
          {MEMBER_ROLE_LABELS[role] || role}s ({members.length})
        </Typography>
      </Stack>
      <Grid container spacing={1.5}>
        {members.map((member) => (
          <Grid item xs={12} sm={6} key={member.id}>
            <MemberCard member={member} />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}

RoleGroup.propTypes = {
  role: PropTypes.string.isRequired,
  members: PropTypes.array.isRequired
};

// ==============================|| CAMPAIGN MEMBERS TAB ||============================== //

export default function CampaignMembersTab({ campaignId, campaign }) {
  const theme = useTheme();

  // TODO: Replace with real API hook when backend is ready
  const members = MOCK_MEMBERS;

  // Group members by role
  const groupedMembers = ROLE_ORDER.reduce((acc, role) => {
    acc[role] = members.filter((m) => m.role === role);
    return acc;
  }, {});

  // ==============================|| EMPTY STATE ||============================== //

  if (members.length === 0) {
    return (
      <Box sx={{ py: 6, textAlign: 'center' }}>
        <Typography variant="h5" color="text.secondary">
          No members in this campaign
        </Typography>
        <Typography variant="body2" color="text.disabled" sx={{ mt: 1 }}>
          Add team members to collaborate on this campaign.
        </Typography>
      </Box>
    );
  }

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      {/* Header */}
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
        <Typography variant="body2" color="text.secondary">
          {members.length} member{members.length !== 1 ? 's' : ''} in this campaign
        </Typography>
        <Button
          variant="outlined"
          size="small"
          startIcon={<PlusOutlined />}
          onClick={() => console.log('TODO: Add member')}
        >
          Add Member
        </Button>
      </Stack>

      {/* Role Groups */}
      <Stack spacing={3}>
        {ROLE_ORDER.map((role) => (
          <RoleGroup key={role} role={role} members={groupedMembers[role] || []} />
        ))}
      </Stack>
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

CampaignMembersTab.propTypes = {
  campaignId: PropTypes.string,
  campaign: PropTypes.object
};