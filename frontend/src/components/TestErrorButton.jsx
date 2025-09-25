'use client';

import { useState } from 'react';
import Button from '@mui/material/Button';

export default function TestErrorButton() {
  const [shouldCrash, setShouldCrash] = useState(false);

  if (shouldCrash) {
    // Déclencher une vraie erreur React
    throw new Error('Test Error: This is a deliberate crash to test ErrorBoundary!');
  }

  // Uniquement visible en dev
  if (process.env.NODE_ENV !== 'development') {
    return null;
  }

  return (
    <Button
      variant="outlined"
      color="error"
      size="small"
      onClick={() => setShouldCrash(true)}
      sx={{
        position: 'fixed',
        bottom: 80,
        right: 16,
        zIndex: 1000,
        opacity: 0.7,
        '&:hover': { opacity: 1 }
      }}
    >
      🐛 Test Error
    </Button>
  );
}