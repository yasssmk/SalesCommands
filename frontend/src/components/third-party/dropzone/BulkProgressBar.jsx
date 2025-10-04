import PropTypes from 'prop-types';

// material-ui
import { useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';

// assets
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';
import CloseCircleOutlined from '@ant-design/icons/CloseCircleOutlined';
import SyncOutlined from '@ant-design/icons/SyncOutlined';
import ClockCircleOutlined from '@ant-design/icons/ClockCircleOutlined';

// ==============================|| BULK OPERATION PROGRESS BAR ||============================== //

export default function BulkProgressBar({
  total = 0,
  processed = 0,
  success = 0,
  failed = 0,
  skipped = 0,
  operation = 'Processing',
  showDetails = true,
  variant = 'default',
  sx = {}
}) {
  const theme = useTheme();
  
  // Calculate percentage
  const percentage = total > 0 ? Math.round((processed / total) * 100) : 0;
  const isComplete = processed >= total && total > 0;
  const hasErrors = failed > 0 || skipped > 0;
  
  // Determine color based on status
  const getProgressColor = () => {
    if (isComplete && !hasErrors) return 'success';
    if (hasErrors) return 'warning';
    return 'primary';
  };
  
  // Formatted operation text
  const operationText = isComplete 
    ? `${operation} Complete` 
    : `${operation} in Progress`;
  
  // Render minimal variant (just the progress bar)
  if (variant === 'minimal') {
    return (
      <Box sx={{ width: '100%', ...sx }}>
        <LinearProgress
          variant="determinate"
          value={percentage}
          color={getProgressColor()}
          sx={{ height: 8, borderRadius: 4 }}
        />
      </Box>
    );
  }
  
  // Render inline variant (progress bar with text)
  if (variant === 'inline') {
    return (
      <Stack spacing={1} sx={{ width: '100%', ...sx }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Typography variant="body2" color="textSecondary">
            {operationText}
          </Typography>
          <Typography variant="body2" color="textSecondary">
            {percentage}%
          </Typography>
        </Stack>
        <LinearProgress
          variant="determinate"
          value={percentage}
          color={getProgressColor()}
          sx={{ height: 8, borderRadius: 4 }}
        />
        {showDetails && (
          <Typography variant="caption" color="textSecondary">
            {processed} of {total} processed
          </Typography>
        )}
      </Stack>
    );
  }
  
  // Default variant - full card with details
  return (
    <Card sx={{ p: 2.5, ...sx }}>
      <Stack spacing={2}>
        {/* Header */}
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Stack direction="row" spacing={1} alignItems="center">
            {isComplete ? (
              hasErrors ? (
                <CloseCircleOutlined style={{ color: theme.palette.warning.main, fontSize: 20 }} />
              ) : (
                <CheckCircleOutlined style={{ color: theme.palette.success.main, fontSize: 20 }} />
              )
            ) : (
              <SyncOutlined spin style={{ color: theme.palette.primary.main, fontSize: 20 }} />
            )}
            <Typography variant="h5">{operationText}</Typography>
          </Stack>
          <Typography variant="h5">{percentage}%</Typography>
        </Stack>
        
        {/* Progress Bar */}
        <LinearProgress
          variant="determinate"
          value={percentage}
          color={getProgressColor()}
          sx={{ height: 10, borderRadius: 5 }}
        />
        
        {/* Stats */}
        {showDetails && (
          <Grid container spacing={2}>
            <Grid item xs={6} sm={3}>
              <Stack spacing={0.5}>
                <Typography variant="caption" color="textSecondary">
                  Total
                </Typography>
                <Stack direction="row" spacing={0.5} alignItems="center">
                  <ClockCircleOutlined style={{ fontSize: 14 }} />
                  <Typography variant="h6">{total}</Typography>
                </Stack>
              </Stack>
            </Grid>
            
            <Grid item xs={6} sm={3}>
              <Stack spacing={0.5}>
                <Typography variant="caption" color="textSecondary">
                  Successful
                </Typography>
                <Stack direction="row" spacing={0.5} alignItems="center">
                  <CheckCircleOutlined style={{ fontSize: 14, color: theme.palette.success.main }} />
                  <Typography variant="h6" color="success.main">
                    {success}
                  </Typography>
                </Stack>
              </Stack>
            </Grid>
            
            {failed > 0 && (
              <Grid item xs={6} sm={3}>
                <Stack spacing={0.5}>
                  <Typography variant="caption" color="textSecondary">
                    Failed
                  </Typography>
                  <Stack direction="row" spacing={0.5} alignItems="center">
                    <CloseCircleOutlined style={{ fontSize: 14, color: theme.palette.error.main }} />
                    <Typography variant="h6" color="error.main">
                      {failed}
                    </Typography>
                  </Stack>
                </Stack>
              </Grid>
            )}
            
            {skipped > 0 && (
              <Grid item xs={6} sm={3}>
                <Stack spacing={0.5}>
                  <Typography variant="caption" color="textSecondary">
                    Skipped
                  </Typography>
                  <Stack direction="row" spacing={0.5} alignItems="center">
                    <CloseCircleOutlined style={{ fontSize: 14, color: theme.palette.warning.main }} />
                    <Typography variant="h6" color="warning.main">
                      {skipped}
                    </Typography>
                  </Stack>
                </Stack>
              </Grid>
            )}
          </Grid>
        )}
        
        {/* Summary chips for inline info */}
        {!showDetails && processed > 0 && (
          <Stack direction="row" spacing={1}>
            <Chip
              icon={<CheckCircleOutlined />}
              label={`${success} success`}
              size="small"
              color="success"
              variant="light"
            />
            {failed > 0 && (
              <Chip
                icon={<CloseCircleOutlined />}
                label={`${failed} failed`}
                size="small"
                color="error"
                variant="light"
              />
            )}
            {skipped > 0 && (
              <Chip
                icon={<CloseCircleOutlined />}
                label={`${skipped} skipped`}
                size="small"
                color="warning"
                variant="light"
              />
            )}
          </Stack>
        )}
      </Stack>
    </Card>
  );
}

BulkProgressBar.propTypes = {
  total: PropTypes.number,
  processed: PropTypes.number,
  success: PropTypes.number,
  failed: PropTypes.number,
  skipped: PropTypes.number,
  operation: PropTypes.string,
  showDetails: PropTypes.bool,
  variant: PropTypes.oneOf(['default', 'inline', 'minimal']),
  sx: PropTypes.object
};