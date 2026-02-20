// frontend/src/sections/campaigns/workspace/CampaignOverviewTab.jsx
/**
 * Campaign Overview Tab — Placeholder.
 *
 * Will contain dashboard KPIs, charts, and progress overview.
 * For now: "Coming Soon" message.
 */

'use client';

import PropTypes from 'prop-types';

// MUI
import { useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// icons
import DashboardOutlined from '@ant-design/icons/DashboardOutlined';

// ==============================|| CAMPAIGN OVERVIEW TAB ||============================== //

export default function CampaignOverviewTab({ campaign }) {
  const theme = useTheme();

  return (
    <Box
      sx={{
        py: 8,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center'
      }}
    >
      <Stack spacing={2} alignItems="center" sx={{ maxWidth: 400, textAlign: 'center' }}>
        <Box
          sx={{
            width: 64,
            height: 64,
            borderRadius: 2,
            bgcolor: 'grey.100',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          <DashboardOutlined style={{ fontSize: 32, color: theme.palette.text.disabled }} />
        </Box>
        <Typography variant="h5" color="text.secondary">
          Dashboard coming soon
        </Typography>
        <Typography variant="body2" color="text.disabled">
          Campaign KPIs, progress charts, and activity analytics will be available here in a future release.
        </Typography>
      </Stack>
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

CampaignOverviewTab.propTypes = {
  campaign: PropTypes.object
};