// frontend/src/app/coming-soon-wip/page.js

'use client';

import { useSearchParams } from 'next/navigation';
import { useEffect } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Container from '@mui/material/Container';
import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';

// project imports
import { APP_DEFAULT_PATH } from 'config';
import MainCard from 'components/MainCard';

// assets
import ToolOutlined from '@ant-design/icons/ToolOutlined';
import HomeOutlined from '@ant-design/icons/HomeOutlined';
import RocketOutlined from '@ant-design/icons/RocketOutlined';
import ClockCircleOutlined from '@ant-design/icons/ClockCircleOutlined';

// ==============================|| COMING SOON WIP - MAIN ||============================== //

/**
 * Generic Coming Soon page for Work In Progress features
 * Internal business application - Client access only
 * 
 * USAGE:
 * - Direct access: /coming-soon-wip
 * - With context: /coming-soon-wip?feature=teams&section=admin
 * 
 * FEATURES:
 * - Dynamic title based on query params
 * - Development tracking (logs WIP clicks)
 * - Clean UI with icon variations
 * - Always returns 200 (not 404)
 */

export default function ComingSoonWIP() {
  const searchParams = useSearchParams();
  
  // Extract context from URL params
  const feature = searchParams.get('feature') || 'page';
  const section = searchParams.get('section') || '';
  
  // Track WIP page views in development
  useEffect(() => {
    if (process.env.NODE_ENV === 'development') {
      console.log('[WIP Access]', {
        feature,
        section,
        timestamp: new Date().toISOString(),
        referrer: document.referrer || 'direct'
      });
    }
    
    // TODO: Add internal analytics/telemetry if needed
    // Example: trackEvent('wip_page_view', { feature, section })
  }, [feature, section]);
  
  // Build dynamic title
  const getTitle = () => {
    const featureName = feature.charAt(0).toUpperCase() + feature.slice(1);
    const sectionName = section ? `${section.charAt(0).toUpperCase() + section.slice(1)} ` : '';
    return `${sectionName}${featureName}`;
  };
  
  // Select icon based on feature type
  const getIcon = () => {
    switch(feature) {
      case 'teams':
      case 'organizations':
        return <RocketOutlined style={{ fontSize: '4rem', color: '#1890ff' }} />;
      case 'roles':
      case 'permissions':
        return <ToolOutlined style={{ fontSize: '4rem', color: '#1890ff' }} />;
      default:
        return <ClockCircleOutlined style={{ fontSize: '4rem', color: '#1890ff' }} />;
    }
  };

  return (
    <Container maxWidth="sm">
      <Grid 
        container 
        spacing={3} 
        direction="column" 
        alignItems="center" 
        justifyContent="center" 
        sx={{ minHeight: 'calc(100vh - 200px)', py: 4 }}
      >
        <Grid item xs={12}>
          <MainCard 
            sx={{ 
              textAlign: 'center',
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              color: 'white'
            }}
          >
            <Box sx={{ p: 3 }}>
              {getIcon()}
            </Box>
          </MainCard>
        </Grid>
        
        <Grid item xs={12}>
          <Paper elevation={0} sx={{ p: 4, textAlign: 'center', bgcolor: 'transparent' }}>
            <Stack spacing={2} alignItems="center">
              <Typography variant="h1" gutterBottom>
                {getTitle()} Coming Soon
              </Typography>
              
              <Typography variant="h5" color="text.secondary" sx={{ maxWidth: 450 }}>
                We're working hard to bring you this feature.
              </Typography>
              
              <Typography variant="body1" color="text.secondary" sx={{ maxWidth: 450, mt: 1 }}>
                This section is currently under development and will be available in a future release. 
                Check back soon for updates!
              </Typography>
              
              <Box sx={{ mt: 4 }}>
                <Stack direction="row" spacing={2}>
                  <Button 
                    variant="contained" 
                    startIcon={<HomeOutlined />}
                    href={APP_DEFAULT_PATH}
                    size="large"
                  >
                    Back to Dashboard
                  </Button>
                  
                  {process.env.NODE_ENV === 'development' && (
                    <Button 
                      variant="outlined"
                      onClick={() => {
                        console.log('[WIP Debug]', { feature, section });
                        alert(`Feature: ${feature}\nSection: ${section}\n\nThis is a development-only message.`);
                      }}
                    >
                      Dev Info
                    </Button>
                  )}
                </Stack>
              </Box>
              
              {/* Development mode indicator */}
              {process.env.NODE_ENV === 'development' && (
                <Box sx={{ mt: 3, p: 2, bgcolor: 'warning.light', borderRadius: 1 }}>
                  <Typography variant="caption" color="warning.dark">
                    DEV MODE: Feature={feature} | Section={section}
                  </Typography>
                </Box>
              )}
            </Stack>
          </Paper>
        </Grid>
        
        {/* Feature status for internal tracking */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
            <Stack direction="row" spacing={2} justifyContent="center" alignItems="center">
              <Typography variant="caption" color="text.secondary">
                Development Status:
              </Typography>
              <Typography variant="subtitle2" color="primary">
                In Progress
              </Typography>
            </Stack>
          </Paper>
        </Grid>
      </Grid>
    </Container>
  );
}

// Note: This is an internal business app (like Salesforce)
// No SEO/metadata needed as it's not public-facing