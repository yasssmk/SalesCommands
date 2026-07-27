// frontend/src/sections/objectives/ObjectiveCard.jsx
//
// One objective row/card: metric, period + its derived state chip, target,
// current value, and the progress bar. The attainment RATIO comes straight from
// the API payload (`progress_ratio`, non-clamped) — never recomputed here. When
// it is > 1 the bar renders the over-achievement style (star + real % +
// warning.dark) via GoalProgressRow's optional prop.

import PropTypes from 'prop-types';

import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

import EditOutlined from '@ant-design/icons/EditOutlined';
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';

import MainCard from 'components/MainCard';
import GoalProgressRow from 'sections/home/GoalProgressRow';
import { goalGradient } from 'sections/home/utils/goalGradient';
import { formatDateOnly } from 'config/formatters';

import PeriodStateChip from './PeriodStateChip';
import { metricLabel, isMonetaryMetric } from './metricLabels';

export default function ObjectiveCard({ objective, onEdit, onDelete }) {
  const {
    metric,
    target_value,
    current_value,
    progress_ratio,
    period_start,
    period_end,
    state,
  } = objective;

  const monetary = isMonetaryMetric(metric);
  const target = Number(target_value) || 0;
  const current = Number(current_value) || 0;
  const unit = monetary ? '$' : '';

  // Headline / bar % for the <= 1 case; the raw ratio drives over-achievement.
  const gradient = goalGradient(current, target, { unit });
  const ratio = progress_ratio == null ? null : Number(progress_ratio);

  const fmtValue = (n) => (monetary ? n.toLocaleString() : n);

  return (
    <MainCard>
      <Stack spacing={1}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
          <Stack direction="row" alignItems="center" spacing={1}>
            <Typography variant="subtitle1">{metricLabel(metric)}</Typography>
            <PeriodStateChip state={state} />
          </Stack>
          <Stack direction="row" spacing={0.5}>
            <Tooltip title="Edit">
              <IconButton size="small" aria-label="edit objective" onClick={() => onEdit?.(objective)}>
                <EditOutlined />
              </IconButton>
            </Tooltip>
            <Tooltip title="Delete">
              <IconButton size="small" aria-label="delete objective" onClick={() => onDelete?.(objective)}>
                <DeleteOutlined />
              </IconButton>
            </Tooltip>
          </Stack>
        </Stack>

        <Typography variant="body2" color="text.secondary">
          Target {fmtValue(target)}{unit ? ` ${unit}` : ''} · {formatDateOnly(period_start)} → {formatDateOnly(period_end)}
        </Typography>

        <Box>
          <GoalProgressRow
            label={`${fmtValue(current)} so far`}
            gradient={gradient}
            overAchievementRatio={ratio}
          />
        </Box>
      </Stack>
    </MainCard>
  );
}

ObjectiveCard.propTypes = {
  objective: PropTypes.shape({
    id: PropTypes.string,
    metric: PropTypes.string,
    target_value: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    current_value: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    progress_ratio: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    period_start: PropTypes.string,
    period_end: PropTypes.string,
    state: PropTypes.string,
  }).isRequired,
  onEdit: PropTypes.func,
  onDelete: PropTypes.func,
};
