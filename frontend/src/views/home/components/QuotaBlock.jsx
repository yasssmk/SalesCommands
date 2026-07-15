// frontend/src/views/home/components/QuotaBlock.jsx

import PropTypes from 'prop-types';

import Grid from '@mui/material/Unstable_Grid2';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import MainCard from 'components/MainCard';
import LinearWithLabel from 'components/@extended/progress/LinearWithLabel';

import { goalGradient } from 'views/home/utils/goalGradient';
import { unitFor, labelForType, fmtVal } from 'views/home/utils/quotaFormat';

// ==============================|| QUOTA BLOCK — where I am vs target ||============================== //

/**
 * "Where I am" — quota attainment: result vs target, framed as what's LEFT when
 * near the finish (goal gradient). One card per active in-period quota (a rep
 * may hold several by target_type). We do not invent a "primary" quota.
 */
export default function QuotaBlock({ quotas = [], loading = false }) {
  if (loading) {
    return (
      <Grid container spacing={2}>
        {[0, 1].map((i) => (
          <Grid xs={12} md={6} key={i}>
            <Skeleton variant="rounded" height={140} />
          </Grid>
        ))}
      </Grid>
    );
  }

  if (!quotas.length) {
    return (
      <MainCard>
        <Typography variant="body2" color="text.secondary">
          No active quota for this period.
        </Typography>
      </MainCard>
    );
  }

  return (
    <Grid container spacing={2}>
      {quotas.map(({ entity, result }) => {
        const meta = result?.meta || {};
        const unit = unitFor(meta.target_type);
        const hasCounts = meta.current != null && meta.target != null;
        const g = hasCounts ? goalGradient(meta.current, meta.target, { unit }) : null;
        const title = entity.name || labelForType(meta.target_type);

        return (
          <Grid xs={12} md={6} key={entity.id}>
            <MainCard>
              <Stack spacing={1}>
                <Typography variant="subtitle1">{title}</Typography>
                {g ? (
                  <>
                    <Typography
                      variant="h4"
                      color={g.mode === 'done' ? 'success.main' : g.mode === 'remaining' ? 'warning.main' : 'primary.main'}
                    >
                      {g.headline}
                    </Typography>
                    <LinearWithLabel value={g.pct} color={g.pct >= 100 ? 'success' : 'primary'} />
                    <Typography variant="caption" color="text.secondary">
                      {fmtVal(meta.current, unit)} of {fmtVal(meta.target, unit)}
                    </Typography>
                  </>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    {typeof result?.value === 'number' ? `${result.value}% attained` : 'Not available yet.'}
                  </Typography>
                )}
              </Stack>
            </MainCard>
          </Grid>
        );
      })}
    </Grid>
  );
}

QuotaBlock.propTypes = {
  quotas: PropTypes.array,
  loading: PropTypes.bool,
};
