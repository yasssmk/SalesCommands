import PropTypes from 'prop-types';
// material-ui
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import Box from '@mui/material/Box';

// ==============================|| PROGRESS - LINEAR WITH LABEL ||============================== //

export default function LinearWithLabel({ value, ...others }) {
  return (
    <Stack alignItems="center" direction="row">
      <Box sx={{ width: '100%', mr: 1 }}>
        <LinearProgress variant="determinate" value={value} {...others} />
      </Box>
      <Box sx={{ minWidth: 35 }}>
        <Typography variant="body2" color="text.secondary">{`${Math.round(value)}%`}</Typography>
      </Box>
    </Stack>
  );
}

LinearWithLabel.propTypes = { value: PropTypes.any, others: PropTypes.any };
