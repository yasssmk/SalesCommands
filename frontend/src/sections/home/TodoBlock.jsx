// frontend/src/sections/home/TodoBlock.jsx

import PropTypes from 'prop-types';

import Grid from '@mui/material/Grid';
import Skeleton from '@mui/material/Skeleton';

import ClockCircleOutlined from '@ant-design/icons/ClockCircleOutlined';
import ExclamationCircleOutlined from '@ant-design/icons/ExclamationCircleOutlined';
import CalendarOutlined from '@ant-design/icons/CalendarOutlined';
import ScheduleOutlined from '@ant-design/icons/ScheduleOutlined';

import { TODO_WINDOWS } from 'api/bi/todo';

import StatTile from './StatTile';

// ==============================|| TODO BLOCK — 4 clickable window tiles ||============================== //

const iconSx = { fontSize: 18 };

/**
 * The rep's todo tiles: overdue / today / next 7 days / next 4 weeks. Each tile
 * is a filter button — clicking it drives the table below (onSelect), the active
 * one is outlined. Windows are ROLLING (not calendar) so the horizon never
 * collapses at a month/week boundary. The count is the motivating
 * smallest-number; overdue turns red to drive the chase.
 */
export default function TodoBlock({ windows = {}, activeFilter, onSelect, loading = false }) {
  if (loading) {
    return (
      <Grid container spacing={2}>
        {[0, 1, 2, 3].map((i) => (
          <Grid item xs={6} sm={3} key={i}>
            <Skeleton variant="rounded" height={112} />
          </Grid>
        ))}
      </Grid>
    );
  }

  const overdue = windows[TODO_WINDOWS.OVERDUE] || 0;

  const tiles = [
    {
      key: TODO_WINDOWS.OVERDUE,
      title: 'Overdue',
      color: overdue > 0 ? 'error' : 'success',
      caption: overdue > 0 ? 'chase these first' : 'nothing overdue',
      icon: <ExclamationCircleOutlined style={iconSx} />,
    },
    {
      key: TODO_WINDOWS.TODAY,
      title: 'Today',
      color: 'primary',
      caption: (windows[TODO_WINDOWS.TODAY] || 0) === 0 ? 'all clear for today' : 'to do today',
      icon: <ClockCircleOutlined style={iconSx} />,
    },
    {
      key: TODO_WINDOWS.NEXT_7_DAYS,
      title: 'Next 7 days',
      color: 'info',
      caption: 'due within 7 days',
      icon: <CalendarOutlined style={iconSx} />,
    },
    {
      key: TODO_WINDOWS.NEXT_4_WEEKS,
      title: 'Next 4 weeks',
      color: 'secondary',
      caption: 'due within 4 weeks',
      icon: <ScheduleOutlined style={iconSx} />,
    },
  ];

  return (
    <Grid container spacing={2}>
      {tiles.map((t) => (
        <Grid item xs={6} sm={3} key={t.key}>
          <StatTile
            title={t.title}
            count={windows[t.key] || 0}
            color={t.color}
            caption={t.caption}
            icon={t.icon}
            onClick={() => onSelect(t.key)}
            active={activeFilter === t.key}
          />
        </Grid>
      ))}
    </Grid>
  );
}

TodoBlock.propTypes = {
  windows: PropTypes.object,
  activeFilter: PropTypes.string,
  onSelect: PropTypes.func,
  loading: PropTypes.bool,
};
