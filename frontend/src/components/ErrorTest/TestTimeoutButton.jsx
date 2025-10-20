// frontend/src/components/ErrorTest/TestTimeoutButton.jsx

/**
 * ✅ COMPOSANT DE TEST TEMPORAIRE - À SUPPRIMER APRÈS VALIDATION
 * 
 * Teste les 4 profils de timeout avec affichage en temps réel :
 * - CRITICAL (8s) : GET requests principales
 * - WIDGET (4s)   : Dashboards, stats rapides
 * - MUTATION (10s): POST/PUT/PATCH/DELETE
 * - BULK (60s)    : Import/export, bulk operations
 * 
 * Usage :
 * 1. Importer dans une page (ex: views/admin/users/list.jsx)
 * 2. Ajouter <TestTimeoutButton /> dans le render
 * 3. Tester chaque profil avec les boutons
 * 4. Observer console + snackbar + temps écoulé
 * 5. Supprimer après validation
 * 
 * Prérequis backend (ÉTAPE 5) :
 * - Endpoint GET/POST /ops/sleep/<seconds>/ qui fait time.sleep(seconds)
 */

'use client';

import { useState } from 'react';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Divider from '@mui/material/Divider';
import BugOutlined from '@ant-design/icons/BugOutlined';
import ClockCircleOutlined from '@ant-design/icons/ClockCircleOutlined';
import ThunderboltOutlined from '@ant-design/icons/ThunderboltOutlined';
import { api } from 'utils/axiosClient';
import { authConfig } from 'config/auth';

// ==============================|| TEST PROFILES ||============================== //

const TEST_PROFILES = [
  {
    name: 'CRITICAL',
    timeout: authConfig.TIMEOUT_PROFILES.CRITICAL,
    sleepDuration: 12, // 12s (> 8s timeout)
    method: 'GET',
    color: 'primary',
    description: 'Main data fetching (users, accounts)',
    icon: <ThunderboltOutlined />
  },
  {
    name: 'WIDGET',
    timeout: authConfig.TIMEOUT_PROFILES.WIDGET,
    sleepDuration: 6, // 6s (> 4s timeout)
    method: 'GET',
    color: 'info',
    description: 'Dashboard widgets, quick stats',
    icon: <ClockCircleOutlined />
  },
  {
    name: 'MUTATION',
    timeout: authConfig.TIMEOUT_PROFILES.MUTATION,
    sleepDuration: 12, // 12s (> 10s timeout)
    method: 'POST',
    color: 'warning',
    description: 'Form submissions (POST/PUT/PATCH)',
    icon: <BugOutlined />
  },
  {
    name: 'BULK',
    timeout: authConfig.TIMEOUT_PROFILES.BULK,
    sleepDuration: 65, // 65s (> 60s timeout)
    method: 'POST',
    color: 'secondary',
    description: 'Bulk operations (import/export)',
    icon: <BugOutlined />
  }
];

// ==============================|| MAIN COMPONENT ||============================== //

export default function TestTimeoutButton() {
  const [results, setResults] = useState({});
  const [loading, setLoading] = useState({});

  // Only visible in dev
  if (process.env.NODE_ENV !== 'development') {
    return null;
  }

  /**
   * Test a specific timeout profile
   */
  const testProfile = async (profile) => {
    const profileName = profile.name;
    
    console.group(`🧪 [Timeout Test] ${profileName} Profile`);
    console.log('Expected timeout:', `${profile.timeout}ms`);
    console.log('Backend sleep:', `${profile.sleepDuration}s`);
    console.log('Should timeout:', profile.sleepDuration * 1000 > profile.timeout ? 'YES' : 'NO');
    
    setLoading(prev => ({ ...prev, [profileName]: true }));
    setResults(prev => ({ ...prev, [profileName]: null }));

    const startTime = Date.now();
    
    try {
      // Construct endpoint (will be created in ÉTAPE 5)
      const endpoint = `/ops/sleep/${profile.sleepDuration}/`;
      
      // Call with explicit profile
      let result;
      if (profile.method === 'GET') {
        result = await api.get(endpoint, { profile: profile.name.toLowerCase() });
      } else {
        result = await api.post(endpoint, {}, { profile: profile.name.toLowerCase() });
      }
      
      const duration = Date.now() - startTime;
      
      console.log('✅ Request succeeded (no timeout)');
      console.log('Duration:', `${duration}ms`);
      console.log('Result:', result);
      console.groupEnd();
      
      setResults(prev => ({
        ...prev,
        [profileName]: {
          success: true,
          duration,
          message: `Completed in ${(duration / 1000).toFixed(2)}s`,
          data: result.data
        }
      }));
      
    } catch (error) {
      const duration = Date.now() - startTime;
      
      console.error('❌ Request failed');
      console.log('Duration:', `${duration}ms`);
      console.log('Status:', error.status || error.response?.status);
      console.log('isTimeout:', error.isTimeout);
      console.log('Message:', error.message);
      console.groupEnd();
      
      setResults(prev => ({
        ...prev,
        [profileName]: {
          success: false,
          duration,
          status: error.status || error.response?.status || 0,
          isTimeout: error.isTimeout || false,
          message: error.message || 'Unknown error'
        }
      }));
    } finally {
      setLoading(prev => ({ ...prev, [profileName]: false }));
    }
  };

  /**
   * Clear all results
   */
  const clearResults = () => {
    setResults({});
  };

  return (
    <Card
      sx={{
        position: 'fixed',
        bottom: 16,
        right: 16,
        zIndex: 1300,
        maxWidth: 400,
        opacity: 0.95,
        '&:hover': { opacity: 1 }
      }}
    >
      <CardContent>
        <Stack spacing={2}>
          {/* Header */}
          <Box display="flex" alignItems="center" justifyContent="space-between">
            <Typography variant="h5" display="flex" alignItems="center" gap={1}>
              <BugOutlined style={{ fontSize: 20 }} />
              Timeout Tests
            </Typography>
            <Chip label="DEV ONLY" color="error" size="small" />
          </Box>

          <Divider />

          {/* Test Buttons */}
          <Stack spacing={1.5}>
            {TEST_PROFILES.map((profile) => {
              const isLoading = loading[profile.name];
              const result = results[profile.name];

              return (
                <Box key={profile.name}>
                  <Button
                    fullWidth
                    variant="outlined"
                    color={profile.color}
                    onClick={() => testProfile(profile)}
                    disabled={isLoading}
                    startIcon={isLoading ? <CircularProgress size={16} /> : profile.icon}
                    sx={{ justifyContent: 'flex-start', textAlign: 'left' }}
                  >
                    <Stack direction="column" spacing={0.5} flex={1}>
                      <Box display="flex" alignItems="center" gap={1}>
                        <Typography variant="body2" fontWeight="bold">
                          {profile.name}
                        </Typography>
                        <Chip
                          label={`${profile.timeout / 1000}s`}
                          size="small"
                          sx={{ height: 20, fontSize: '0.7rem' }}
                        />
                      </Box>
                      <Typography variant="caption" color="text.secondary">
                        {profile.description}
                      </Typography>
                    </Stack>
                  </Button>

                  {/* Result Display */}
                  {result && (
                    <Box
                      sx={{
                        mt: 0.5,
                        p: 1,
                        borderRadius: 1,
                        bgcolor: result.success ? 'success.lighter' : 'error.lighter'
                      }}
                    >
                      <Stack spacing={0.5}>
                        <Typography variant="caption" fontWeight="bold">
                          {result.success ? '✅ Success' : '❌ Failed'}
                          {result.isTimeout && ' (Timeout)'}
                        </Typography>
                        <Typography variant="caption">
                          Duration: {(result.duration / 1000).toFixed(2)}s
                        </Typography>
                        {result.status > 0 && (
                          <Typography variant="caption">
                            Status: {result.status}
                          </Typography>
                        )}
                        <Typography variant="caption" color="text.secondary">
                          {result.message}
                        </Typography>
                      </Stack>
                    </Box>
                  )}
                </Box>
              );
            })}
          </Stack>

          <Divider />

          {/* Clear Button */}
          <Button
            size="small"
            variant="text"
            onClick={clearResults}
            disabled={Object.keys(results).length === 0}
          >
            Clear Results
          </Button>

          {/* Instructions */}
          <Box sx={{ bgcolor: 'warning.lighter', p: 1.5, borderRadius: 1 }}>
            <Typography variant="caption" fontWeight="bold" display="block" mb={0.5}>
              ⚠️ Prerequisites:
            </Typography>
            <Typography variant="caption" component="div">
              Backend must have <code>/ops/sleep/&lt;seconds&gt;/</code> endpoint
              <br />
              (Created in ÉTAPE 5.1)
            </Typography>
          </Box>

          {/* Expected Behavior */}
          <Box sx={{ bgcolor: 'info.lighter', p: 1.5, borderRadius: 1 }}>
            <Typography variant="caption" fontWeight="bold" display="block" mb={0.5}>
              ℹ️ Expected Behavior:
            </Typography>
            <Typography variant="caption" component="div">
              • All should timeout (sleep &gt; timeout)
              <br />
              • Status: 408
              <br />
              • Snackbar: "Request took too long"
              <br />
              • Check console for retry logs (GET only)
            </Typography>
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );
}