// frontend/src/views/home/components/TodoBlock.jsx

import PropTypes from 'prop-types';

import Grid from '@mui/material/Unstable_Grid2';
import Skeleton from '@mui/material/Skeleton';

import ClockCircleOutlined from '@ant-design/icons/ClockCircleOutlined';
import ExclamationCircleOutlined from '@ant-design/icons/ExclamationCircleOutlined';
import CalendarOutlined from '@ant-design/icons/CalendarOutlined';

import StatTile from './StatTile';

// ==============================|| TODO BLOCK — what I have to do ||============================== //

const iconSx = { fontSize: 18 };

/**
 * Renders the rep's todo buckets (todo_my_activities breakdown). "Today" is the
 * number to act on now; "Overdue" turns red to drive the chase; captions frame
 * the most attainable reading (e.g. "All clear for today" when zero).
 */
export default function TodoBlock({ value = null, loading = false }) {
  if (loading) {
    return (
      <Grid container spacing={2}>
        {[0, 1, 2].map((i) => (
          <Grid xs={12} sm={4} key={i}>
            <Skeleton variant="rounded" height={112} />
          </Grid>
        ))}
      </Grid>
    );
  }

  const v = value || {};
  const today = v.today || 0;
  const overdue = v.overdue || 0;
  const upcoming = v.upcoming || 0;

  return (
    <Grid container spacing={2}>
      <Grid xs={12} sm={4}>
        <StatTile
          title="Today"
          count={today}
          color="primary"
          caption={today === 0 ? 'All clear for today' : 'to do today'}
          icon={<ClockCircleOutlined style={iconSx} />}
        />
      </Grid>
      <Grid xs={12} sm={4}>
        <StatTile
          title="Overdue"
          count={overdue}
          color={overdue > 0 ? 'error' : 'success'}
          caption={overdue > 0 ? 'chase these first' : 'nothing overdue'}
          icon={<ExclamationCircleOutlined style={iconSx} />}
        />
      </Grid>
      <Grid xs={12} sm={4}>
        <StatTile
          title="This week"
          count={upcoming}
          color="info"
          caption="coming up"
          icon={<CalendarOutlined style={iconSx} />}
        />
      </Grid>
    </Grid>
  );
}

TodoBlock.propTypes = {
  value: PropTypes.object,
  loading: PropTypes.bool,
};
