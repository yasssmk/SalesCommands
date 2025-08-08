'use client';
import { Box, Typography, Paper } from '@mui/material';
import SimpleLayout from '../layout/SimpleLayout';

export default function HomePage() {
  return (
    <SimpleLayout>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '60vh'
        }}
      >
        <Paper
          elevation={3}
          sx={{
            p: 6,
            textAlign: 'center',
            maxWidth: 600,
            width: '100%'
          }}
        >
          <Typography variant="h2" color="primary" gutterBottom>
            SalesCommands
          </Typography>
          <Typography variant="h5" color="text.secondary" gutterBottom>
            Votre application est prête !
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mt: 2 }}>
            Le système de thème Material-UI est configuré et fonctionnel.
          </Typography>
        </Paper>
      </Box>
    </SimpleLayout>
  );
}