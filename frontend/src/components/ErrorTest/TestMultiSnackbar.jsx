// frontend/src/components/ErrorTest/TestMultiSnackbar.jsx

/**
 * ✅ COMPOSANT DE TEST TEMPORAIRE - À SUPPRIMER APRÈS VALIDATION
 * 
 * Déclenche plusieurs snackbars simultanément pour tester le stacking NOTISTACK
 * 
 * IMPORTANT: Utilise directement enqueueSnackbar de Notistack
 * (pas displaySnackbar qui utilise le système custom MUI)
 */

import { useState } from 'react';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import BugOutlined from '@ant-design/icons/BugOutlined';
import { useSnackbar } from 'notistack';

const TestMultiSnackbar = () => {
  const [isRunning, setIsRunning] = useState(false);
  const { enqueueSnackbar } = useSnackbar();

  const triggerMultipleSnackbars = () => {
    setIsRunning(true);

    // Déclencher 5 snackbars avec Notistack directement
    enqueueSnackbar('Import completed successfully', { 
      variant: 'success',
      autoHideDuration: 3000
    });
    
    setTimeout(() => {
      enqueueSnackbar('2 users were skipped due to duplicate emails', { 
        variant: 'warning',
        autoHideDuration: 5000
      });
    }, 100);
    
    setTimeout(() => {
      enqueueSnackbar('You have 5 seats remaining in your plan', { 
        variant: 'info',
        autoHideDuration: 4000
      });
    }, 200);

    setTimeout(() => {
      enqueueSnackbar('Network connection lost', { 
        variant: 'error',
        autoHideDuration: 6000
      });
      enqueueSnackbar('Failed to sync with server', { 
        variant: 'error',
        autoHideDuration: 6000
      });
    }, 2000);

    setTimeout(() => setIsRunning(false), 3000);
  };

  return (
    <Stack direction="row" spacing={2} alignItems="center" sx={{ p: 2, bgcolor: 'warning.lighter', borderRadius: 1 }}>
      <BugOutlined style={{ fontSize: 20 }} />
      <Typography variant="body2">
        <strong>Test Multi-Snackbar (Notistack):</strong> Cliquez pour voir 5 notifications empilées
      </Typography>
      <Button
        variant="contained"
        color="warning"
        size="small"
        onClick={triggerMultipleSnackbars}
        disabled={isRunning}
      >
        {isRunning ? 'Testing...' : 'Test Stacking'}
      </Button>
    </Stack>
  );
};

export default TestMultiSnackbar;
