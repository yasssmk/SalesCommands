// frontend/src/views/home/components/StatTile.jsx

import PropTypes from 'prop-types';

import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import MainCard from 'components/MainCard';

// ==============================|| STAT TILE — one framed number + visual cue ||============================== //

/**
 * A single "smallest-number" tile: a title, a large count, an optional caption,
 * and a leading @ant-design icon. Used by the todo block.
 */
export default function StatTile({ title, count, caption, color = 'primary', icon = null }) {
  return (
    <MainCard contentSX={{ p: 2 }}>
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
};
