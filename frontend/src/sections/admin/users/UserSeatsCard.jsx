import PropTypes from 'prop-types';

// material-ui
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
        color: '#fff',
        transform: 'rotate(25deg)',
        '& svg': { width: '100px', height: '100px', opacity: 0.35 }
      }}
    >
      {children}
    </Box>
  );
}

export default function UserSeatsCard({ primary, secondary, iconPrimary, color = 'primary.main' }) {
  const IconPrimary = iconPrimary;
  const primaryIcon = IconPrimary ? <IconPrimary /> : null;

  return (
    <Card elevation={0} sx={{ bgcolor: color, position: 'relative', color: '#fff' }}>
      <CardContent>
        <IconWrapper>{primaryIcon}</IconWrapper>
        <Grid container direction="column" justifyContent="center" alignItems="center" spacing={1}>
          <Grid item>
            <Typography variant="h3" align="center" color="inherit">
              {secondary}
            </Typography>
          </Grid>
          <Grid item>
            <Typography variant="body1" align="center" color="inherit">
              {primary}
            </Typography>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
}

IconWrapper.propTypes = { children: PropTypes.node };

UserSeatsCard.propTypes = {
  primary: PropTypes.string,          // label (e.g., "Seats")
  secondary: PropTypes.oneOfType([    // big number
    PropTypes.string,
    PropTypes.number
  ]),
  iconPrimary: PropTypes.any,         // optional AntD icon component
  color: PropTypes.string             // MUI theme color token
};
