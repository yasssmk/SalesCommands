// frontend/src/sections/activities/workspace/PrepCallEmptyState.jsx
'use client';

import PropTypes from 'prop-types';

// MUI
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// Icons
import { BulbOutlined } from '@ant-design/icons';

// ==============================|| PREP CALL — EMPTY STATE ||============================== //

export default function PrepCallEmptyState({ onGenerate, isGenerating, error }) {
  return (
    <Box
      display="flex"
      justifyContent="center"
      alignItems="center"
      minHeight="300px"
    >
      <Stack spacing={2} alignItems="center" textAlign="center">
        <BulbOutlined style={{ fontSize: 48, color: '#8c8c8c' }} />
        <Typography variant="h5" color="text.secondary">
          Prepare this call
        </Typography>
        <Typography variant="body2" color="text.secondary" maxWidth={400}>
          Generate a tactical brief using validated signals, deal health
          insights, and your decision cycle context.
        </Typography>
        {error && (
          <Typography variant="body2" color="error">
            {error}
          </Typography>
        )}
        <Button
          variant="contained"
          onClick={onGenerate}
          disabled={isGenerating}
          startIcon={isGenerating ? <CircularProgress size={16} color="inherit" /> : null}
        >
          {isGenerating ? 'Generating…' : 'Generate brief'}
        </Button>
      </Stack>
    </Box>
  );
}

PrepCallEmptyState.propTypes = {
  onGenerate: PropTypes.func.isRequired,
  isGenerating: PropTypes.bool.isRequired,
  error: PropTypes.string,
};
