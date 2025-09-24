'use client';
import Grid from '@mui/material/Grid';
import UserCountCard from 'sections/admin/users/UserSeatsCard';
import { useGetClientSeats } from 'api/admin/users';
import { useCurrentUser } from 'hooks/useCurrentUser';

export default function SeatsSummary() {
  // Récupère clientId depuis l’auth courante
  const { currentUser } = useCurrentUser();
  const clientId = currentUser?.client_id || null;
  const clientName = currentUser?.client_name || null;

  // Appelle /client-accounts/:id/stats/ via notre hook
  const { seats, seatsUsed, seatsLeft, seatsLoading } = useGetClientSeats(clientId);

  // Petits placeholders pendant le chargement
  const seatsLabel = seatsLoading ? '…' : String(seats ?? 0);
  const usedLabel = seatsLoading ? '…' : String(seatsUsed ?? 0);
  const leftLabel = seatsLoading ? '…' : String(seatsLeft ?? Math.max(0, (seats || 0) - (seatsUsed || 0)));

  return (
    <>
      <Grid item xs={12} lg={4} sm={6}>
        <UserCountCard primary="Seats" secondary={seatsLabel} color="primary.200" />
      </Grid>
      <Grid item xs={12} lg={4} sm={6}>
        <UserCountCard primary="Seats used" secondary={usedLabel} color="success.light" />
      </Grid>
      <Grid item xs={12} lg={4}>
        <UserCountCard primary="Seats left" secondary={leftLabel} color="info.light" />
      </Grid>
    </>
  );
}
