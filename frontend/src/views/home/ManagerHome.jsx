// frontend/src/views/home/ManagerHome.jsx

'use client';

import Typography from '@mui/material/Typography';

import MainCard from 'components/MainCard';

// ==============================|| MANAGER HOME ||============================== //

/**
 * The manager's observer/control Home (were today's tasks done — with names —
 * and per-person progress). Built in the next step; this placeholder keeps the
 * role switch functional today.
 */
export default function ManagerHome() {
  return (
    <MainCard title="Team overview">
      <Typography variant="body2" color="text.secondary">
        The manager overview is coming next.
      </Typography>
    </MainCard>
  );
}
