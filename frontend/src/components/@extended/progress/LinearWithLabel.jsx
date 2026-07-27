import PropTypes from 'prop-types';
// material-ui
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import Box from '@mui/material/Box';

// ==============================|| PROGRESS - LINEAR WITH LABEL ||============================== //

export default function LinearWithLabel({ value, labelColor = 'text.secondary', ...others }) {
  return (
    <Stack alignItems="center" direction="row">
      <Box sx={{ width: '100%', mr: 1 }}>
        <LinearProgress variant="determinate" value={value} {...others} />
      </Box>
      <Box sx={{ minWidth: 35 }}>
        <Typography variant="body2" color={labelColor}>{`${Math.round(value)}%`}</Typography>
      </Box>
    </Stack>
  );
}

// labelColor is optional (default 'text.secondary'), so existing callers are
// unchanged; the over-achievement row uses it to paint the % in the theme's gold.
LinearWithLabel.propTypes = { value: PropTypes.any, labelColor: PropTypes.any, others: PropTypes.any };
