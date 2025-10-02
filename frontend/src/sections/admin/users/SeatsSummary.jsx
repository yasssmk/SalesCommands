// 'use client';
// import Grid from '@mui/material/Grid';
// import UserCountCard from 'sections/admin/users/UserSeatsCard';
// import { useGetClientSeats } from 'api/admin/users';
// import { useCurrentUser } from 'hooks/useCurrentUser';

// export default function SeatsSummary() {
//   // Récupère clientId depuis l’auth courante
//   const { currentUser } = useCurrentUser();
//   const clientId = currentUser?.client_id || null;
//   const clientName = currentUser?.client_name || null;

//   // Appelle /client-accounts/:id/stats/ via notre hook
//   const { seats, seatsUsed, seatsLeft, seatsLoading } = useGetClientSeats(clientId);

//   // Petits placeholders pendant le chargement
//   const seatsLabel = seatsLoading ? '…' : String(seats ?? 0);
//   const usedLabel = seatsLoading ? '…' : String(seatsUsed ?? 0);
//   const leftLabel = seatsLoading ? '…' : String(seatsLeft ?? Math.max(0, (seats || 0) - (seatsUsed || 0)));

//   return (
//     <>
//       <Grid item xs={12} lg={4} sm={6}>
//         <UserCountCard primary="Seats" secondary={seatsLabel} color='theme.palette.grey[50]' />
//       </Grid>
//       <Grid item xs={12} lg={4} sm={6}>
//         <UserCountCard primary="Seats used" secondary={usedLabel} color="success.light" />
//       </Grid>
//       <Grid item xs={12} lg={4}>
//         <UserCountCard primary="Seats left" secondary={leftLabel} color="info.light" />
//       </Grid>
//     </>
//   );
// }

// SeatsSummary.tsx
'use client';
import Grid from '@mui/material/Grid';
import UserSeatsCard from 'sections/admin/users/UserSeatsCard';
import { useGetClientSeats } from 'api/admin/users';
import { useCurrentUser } from 'hooks/useCurrentUser';

export default function SeatsSummary() {
  const { currentUser } = useCurrentUser();
  const clientId = currentUser?.client_id || null;

  const { seats, seatsUsed, seatsLeft, seatsLoading } = useGetClientSeats(clientId);

  const total = seats ?? 0;
  const used = seatsUsed ?? 0;
  const left = seatsLeft ?? Math.max(0, total - used);
  const ratioUsed = total > 0 ? used / total : 0;
  const ratioLeft = total > 0 ? left / total : 0;

  // helpers: choisit la “teinte” pour le nombre + l’accent
  const usedTone = (() => {
    if (ratioUsed >= 0.9) return { number: 'error.dark', accent: 'error.main' };      // rouge critique
    if (ratioUsed >= 0.7) return { number: 'warning.dark', accent: 'warning.main' };  // orange élevé
    return { number: 'info.dark', accent: 'info.main' };                              // bleu/normal
  })();

  const leftTone = (() => {
    if (left === 0) return { number: 'error.dark', accent: 'error.main' };            // rouge critique
    if (ratioLeft <= 0.3) return { number: 'warning.dark', accent: 'warning.main' };  // orange bas
    return { number: 'success.dark', accent: 'success.main' };                        // vert OK
  })();


  const seatsLabel = seatsLoading ? '…' : String(total);
  const usedLabel = seatsLoading ? '…' : String(used);
  const leftLabel = seatsLoading ? '…' : String(left);

  return (
    <>
      <Grid item xs={12} lg={4} sm={6}>
        <UserSeatsCard
          primary="Seats"
          secondary={seatsLabel}
          numberColor="primary.main"
          accentColor="primary.400"
        />
      </Grid>

      <Grid item xs={12} lg={4} sm={6}>
        <UserSeatsCard
          primary="Seats used"
          secondary={usedLabel}
          numberColor='info.dark'
          accentColor='info.main'
        />
      </Grid>

      <Grid item xs={12} lg={4}>
        <UserSeatsCard
          primary="Seats left"
          secondary={leftLabel}
          numberColor={leftTone.number}
          accentColor={leftTone.accent}
        />
      </Grid>
    </>
  );
}
