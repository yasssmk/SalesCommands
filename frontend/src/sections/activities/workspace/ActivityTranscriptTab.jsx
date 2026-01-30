'use client';

import PropTypes from 'prop-types';

// MUI
import { useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// Icons
import { FileTextOutlined } from '@ant-design/icons';

// ==============================|| ACTIVITY TRANSCRIPT TAB ||============================== //

export default function ActivityTranscriptTab({ activity }) {
  const theme = useTheme();
  
  return (
    <Box
      display="flex"
      justifyContent="center"
      alignItems="center"
      minHeight="300px"
    >
      <Stack spacing={2} alignItems="center" textAlign="center">
        <FileTextOutlined style={{ fontSize: theme.iconSizes.xxl * 2, color: '#8c8c8c' }} />
        <Typography variant="h5" color="text.secondary">
          Transcript & Emails
        </Typography>
        <Typography variant="body2" color="text.secondary" maxWidth={400}>
          Coming soon — Paste call transcripts or emails here. 
          AI will extract signals and insights automatically.
        </Typography>
      </Stack>
    </Box>
  );
}

ActivityTranscriptTab.propTypes = {
  activity: PropTypes.object
};
