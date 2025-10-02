// import PropTypes from 'prop-types';

// // material-ui
// import Box from '@mui/material/Box';
// import Card from '@mui/material/Card';
// import CardContent from '@mui/material/CardContent';
// import Grid from '@mui/material/Grid';
// import Typography from '@mui/material/Typography';

// function IconWrapper({ children }) {
//   return (
//     <Box
//       sx={{
//         position: 'absolute',
//         left: '-17px',
//         bottom: '-27px',
//         color: '#fff',
//         transform: 'rotate(25deg)',
//         '& svg': { width: '100px', height: '100px', opacity: 0.35 }
//       }}
//     >
//       {children}
//     </Box>
//   );
// }

// export default function UserSeatsCard({ primary, secondary, iconPrimary, color = 'primary.main' }) {
//   const IconPrimary = iconPrimary;
//   const primaryIcon = IconPrimary ? <IconPrimary /> : null;

//   return (
//     <Card elevation={0} sx={{ bgcolor: color, position: 'relative', color: '#fff' }}>
//       <CardContent>
//         <IconWrapper>{primaryIcon}</IconWrapper>
//         <Grid container direction="column" justifyContent="center" alignItems="center" spacing={1}>
//           <Grid item>
//             <Typography variant="h2" align="center" color="primary.dark">
//               {secondary}
//             </Typography>
//           </Grid>
//           <Grid item>
//             <Typography variant="h6" align="center" color="warning.dark">
//               {primary}
//             </Typography>
//           </Grid>
//         </Grid>
//       </CardContent>
//     </Card>
//   );
// }

// IconWrapper.propTypes = { children: PropTypes.node };

// UserSeatsCard.propTypes = {
//   primary: PropTypes.string,          // label (e.g., "Seats")
//   secondary: PropTypes.oneOfType([    // big number
//     PropTypes.string,
//     PropTypes.number
//   ]),
//   iconPrimary: PropTypes.any,         // optional AntD icon component
//   color: PropTypes.string             // MUI theme color token
// };

// sections/admin/users/UserSeatsCard.tsx
import PropTypes from 'prop-types';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';

function IconWrapper({ children }) {
  return (
    <Box
      sx={{
        position: 'absolute',
        left: '-17px',
        bottom: '-27px',
        color: 'secondary.400',
        transform: 'rotate(25deg)',
        '& svg': { width: '100px', height: '100px', opacity: 0.18 }
      }}
    >
      {children}
    </Box>
  );
}

export default function UserSeatsCard({
  primary,
  secondary,
  iconPrimary,
  numberColor = 'primary.main',
  accentColor = 'primary.400'
}) {
  const IconPrimary = iconPrimary;
  const primaryIcon = IconPrimary ? <IconPrimary /> : null;

  return (
    <Card
      elevation={0}
      sx={{
        position: 'relative',
        bgcolor: 'secondary.A100',                   // fond unifié (blanc de la palette)
        border: '1px solid',
        borderColor: 'secondary.200',               // bordure fine
        boxShadow: '0 4px 12px rgba(0,0,0,0.08), 0 2px 6px rgba(0,0,0,0.04)',
        borderRadius: 2,
        overflow: 'hidden'
      }}
    >
      {/* ligne d’accent en haut */}
      <Box sx={{ height: 4, bgcolor: accentColor }} />

      <CardContent sx={{ py: 3.5 }}>
        <IconWrapper>{primaryIcon}</IconWrapper>

        <Grid container direction="column" justifyContent="center" alignItems="center" spacing={0.5}>
          <Grid item>
            <Typography variant="h2" align="center" sx={{ color: numberColor }}>
              {secondary}
            </Typography>
          </Grid>
          <Grid item>
            <Typography variant="h6" align="center" sx={{ color: 'secondary.800' }}>
              {primary}
            </Typography>
          </Grid>
          {/* sous-libellé éventuel */}
          {/* <Typography variant="caption" sx={{ color: 'secondary.600' }}>seats</Typography> */}
        </Grid>
      </CardContent>
    </Card>
  );
}

IconWrapper.propTypes = { children: PropTypes.node };

UserSeatsCard.propTypes = {
  primary: PropTypes.string,
  secondary: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  iconPrimary: PropTypes.any,
  numberColor: PropTypes.string, // couleur du nombre (état)
  accentColor: PropTypes.string  // couleur de la ligne d’accent
};
