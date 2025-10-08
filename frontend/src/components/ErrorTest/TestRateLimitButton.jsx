
// frontend/src/components/TestRateLimitButton.jsx

/**
 * ✅ COMPOSANT DE TEST TEMPORAIRE - À SUPPRIMER APRÈS VALIDATION
 * 
 * Déclenche 20 GET en rafale sur l'endpoint seats pour tester
 * la gestion des 429 (toast, pause SWR, countdown).
 * 
 * Usage :
 * 1. Importer dans views/admin/users/list.jsx
 * 2. Ajouter <TestRateLimitButton /> dans le render
 * 3. Cliquer sur le bouton
 * 4. Observer les logs console et le comportement UI
 * 5. Supprimer ce composant après validation
 */

import { useState } from 'react';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import BugOutlined from '@ant-design/icons/BugOutlined';
import { api } from 'utils/axiosClient';
import { useAuth } from 'hooks/useAuth';

const TestRateLimitButton = () => {
  const { tenantId } = useAuth();
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState(null);

  const runRateLimitTest = async () => {
    if (!tenantId) {
      console.error('[Test 429] No tenantId - please login first');
      return;
    }

    setIsRunning(true);
    setResults(null);

    console.log('🧪 [Test 429] Starting rate limit test with 20 GET requests...');

    // Récupérer le premier client account ID pour le test
    let clientId = null;
    try {
      const clientsResult = await api.get('/client/client-accounts/?page_size=1');
      if (clientsResult.success && clientsResult.data?.results?.[0]?.id) {
        clientId = clientsResult.data.results[0].id;
        console.log(`🧪 [Test 429] Using clientId: ${clientId}`);
      } else {
        console.error('[Test 429] No client accounts found');
        setIsRunning(false);
        return;
      }
    } catch (err) {
      console.error('[Test 429] Failed to fetch client accounts:', err);
      setIsRunning(false);
      return;
    }

    const endpoint = `/client/client-accounts/${clientId}/seats/`;
    
    // Faire 20 GET en rafale (Promise.all = simultané)
    const promises = Array.from({ length: 20 }, (_, i) => {
      return api.get(endpoint)
        .then(result => ({
          index: i + 1,
          status: result.success ? 200 : result.status,
          success: result.success,
          retryAfterMs: result.retryAfterMs || null
        }))
        .catch(err => ({
          index: i + 1,
          status: err.response?.status || 0,
          success: false,
          error: err.message,
          retryAfterMs: err.retryAfterMs || null
        }));
    });

    const results = await Promise.all(promises);
    
    // Analyser les résultats
    const successCount = results.filter(r => r.success).length;
    const errorCount = results.filter(r => !r.success).length;
    const rate429Count = results.filter(r => r.status === 429).length;
    const hasRetryAfter = results.some(r => r.retryAfterMs);

    console.log('🧪 [Test 429] Results:', {
      total: 20,
      success: successCount,
      errors: errorCount,
      rate429: rate429Count,
      hasRetryAfter
    });

    setResults({
      successCount,
      errorCount,
      rate429Count,
      hasRetryAfter,
      details: results
    });

    setIsRunning(false);

    // Log détaillé
    console.group('🧪 [Test 429] Detailed Results');
    results.forEach(r => {
      const emoji = r.success ? '✅' : r.status === 429 ? '⏱️' : '❌';
      console.log(`${emoji} Request ${r.index}: ${r.status}${r.retryAfterMs ? ` (retry after ${Math.ceil(r.retryAfterMs/1000)}s)` : ''}`);
    });
    console.groupEnd();
  };

  // N'afficher ce composant qu'en dev
  if (process.env.NODE_ENV !== 'development') {
    return null;
  }

  return (
    <Box
      sx={{
        position: 'fixed',
        bottom: 20,
        right: 20,
        zIndex: 9999,
        bgcolor: 'warning.lighter',
        border: '2px dashed',
        borderColor: 'warning.main',
        borderRadius: 2,
        p: 2,
        maxWidth: 300
      }}
    >
      <Stack spacing={1.5}>
        <Typography variant="caption" fontWeight={600} color="warning.dark">
          🧪 DEV ONLY - Test Rate Limiting
        </Typography>
        
        <Button
          variant="contained"
          color="warning"
          size="small"
          onClick={runRateLimitTest}
          disabled={isRunning}
          startIcon={<BugOutlined />}
          fullWidth
        >
          {isRunning ? 'Running...' : 'Fire 20 GET Requests'}
        </Button>

        {results && (
          <Box sx={{ p: 1, bgcolor: 'background.paper', borderRadius: 1 }}>
            <Typography variant="caption" display="block">
              ✅ Success: {results.successCount}
            </Typography>
            <Typography variant="caption" display="block">
              ⏱️ 429 errors: {results.rate429Count}
            </Typography>
            <Typography variant="caption" display="block">
              ❌ Other errors: {results.errorCount - results.rate429Count}
            </Typography>
            {results.hasRetryAfter && (
              <Typography variant="caption" display="block" color="success.main" fontWeight={600}>
                ✅ Retry-After detected!
              </Typography>
            )}
          </Box>
        )}

        <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
          Check console logs for details
        </Typography>
      </Stack>
    </Box>
  );
};

export default TestRateLimitButton;