'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

// next
import Link from 'next/link';

// material-ui
import Grid from '@mui/material/Unstable_Grid2';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project import
import AuthWrapper from 'sections/auth/AuthWrapper';
import AuthLogin from 'sections/auth/auth-forms/AuthLogin';

// CHANGEMENT: Utiliser le hook useAuth au lieu de isAuthenticated
import { useAuth, getAuthFlash } from 'hooks/useAuth';
import Loader from 'components/Loader';

// ==============================|| LOGIN PAGE ||============================== //

export default function SignIn() {
  
  const { isAuthenticated, isLoading } = useAuth();
  const [flashError, setFlashError] = useState(null);

  useEffect(() => {
    console.log('🔍 [DEBUG] Login mounted, checking flash...'); // DEBUG
    console.log('🔍 [DEBUG] sessionStorage authFlash:', sessionStorage.getItem('authFlash')); // DEBUG
    
    const flash = getAuthFlash();
    console.log('🔍 [DEBUG] getAuthFlash returned:', flash); // DEBUG
    
    if (flash) {
      setFlashError(flash);
    }
  }, []);
  if (isAuthenticated) {
    return null; 
  }

  // Mock providers and csrfToken for compatibility with model structure
  const providers = null;
  const csrfToken = null;

  return (
    <AuthWrapper>
      <Grid container spacing={3}>
        <Grid xs={12}>
          <Stack direction="row" justifyContent="space-between" alignItems="baseline" sx={{ mb: { xs: -0.5, sm: 0.5 } }}>
            <Typography variant="h3">Login</Typography>
          </Stack>
        </Grid>
        <Grid xs={12}>
          <AuthLogin providers={providers} csrfToken={csrfToken} initialError={flashError} />
        </Grid>
      </Grid>
    </AuthWrapper>
  );
}