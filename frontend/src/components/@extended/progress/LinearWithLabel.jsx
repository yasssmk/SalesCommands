import PropTypes from 'prop-types';
// material-ui
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import Box from '@mui/material/Box';

// ==============================|| PROGRESS - LINEAR WITH LABEL ||============================== //

export default function LinearWithLabel({ value, labelValue, labelColor = 'text.secondary', ...others }) {
  // The bar reads `value`; the label reads `labelValue` when given, else `value`.
  // This decouples the two so an over-achievement bar can be capped to 100 (a
  // FULL bar keeping its normal fill token — MUI shifts the bar off-screen for
  // value > 100, which would render it empty) while the label still shows the
  // real, uncapped percentage. Absent labelValue → label === bar, as before.
  const shownLabel = labelValue == null ? value : labelValue;
  return (
    <Stack alignItems="center" direction="row">
      <Box sx={{ width: '100%', mr: 1 }}>
        <LinearProgress variant="determinate" value={value} {...others} />
      </Box>
      <Box sx={{ minWidth: 35 }}>
        <Typography variant="body2" color={labelColor}>{`${Math.round(shownLabel)}%`}</Typography>
      </Box>
    </Stack>
  );
}

// labelColor is optional (default 'text.secondary'), so existing callers are
// unchanged; the over-achievement row uses it to paint the % in the theme's gold.
// labelValue is optional (default = value); the over-achievement row uses it to
// show the REAL percentage while the bar itself is capped to a full 100.
LinearWithLabel.propTypes = { value: PropTypes.any, labelValue: PropTypes.any, labelColor: PropTypes.any, others: PropTypes.any };
