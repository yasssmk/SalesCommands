// frontend/src/sections/home/StatTile.jsx

import PropTypes from 'prop-types';

import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import MainCard from 'components/MainCard';

// ==============================|| STAT TILE — one framed number + visual cue ||============================== //

/**
 * A single "smallest-number" tile: a title, a large count, an optional caption,
 * and a leading @ant-design icon. When `onClick` is given it acts as a filter
 * button — clickable, and outlined in its color when `active`.
 */
export default function StatTile({ title, count, caption, color = 'primary', icon = null, onClick, active = false }) {
  const clickable = typeof onClick === 'function';
  return (
    <MainCard
      contentSX={{ p: 2 }}
      onClick={onClick}
      sx={{
        ...(clickable && { cursor: 'pointer', transition: 'box-shadow .15s ease' }),
        ...(clickable && !active && { '&:hover': { boxShadow: 2 } }),
        ...(active && { borderColor: `${color}.main`, borderWidth: 2, boxShadow: 3 }),
      }}
    >
      <Stack spacing={0.75}>
        <Stack direction="row" spacing={1} alignItems="center">
          {icon}
          <Typography variant="body2" color="text.secondary">
            {title}
          </Typography>
        </Stack>
        <Typography variant="h3" color={`${color}.main`}>
          {count}
        </Typography>
        {caption ? (
          <Typography variant="caption" color="text.secondary">
            {caption}
          </Typography>
        ) : null}
      </Stack>
    </MainCard>
  );
}

StatTile.propTypes = {
  title: PropTypes.string,
  count: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  caption: PropTypes.string,
  color: PropTypes.string,
  icon: PropTypes.node,
  onClick: PropTypes.func,
  active: PropTypes.bool,
};
