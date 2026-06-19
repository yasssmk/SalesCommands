// frontend/src/sections/activities/workspace/PrepCallBrief.jsx
'use client';

import PropTypes from 'prop-types';

// MUI
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Divider from '@mui/material/Divider';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// Icons
import { SyncOutlined } from '@ant-design/icons';

// ==============================|| BRIEF MODE CHIP COLORS ||============================== //

const MODE_COLORS = {
  DISCOVERY: 'info',
  CONVICTION: 'warning',
  PROOF: 'secondary',
  DECISION: 'success',
};

// ==============================|| PREP CALL — BRIEF DISPLAY ||============================== //

export default function PrepCallBrief({ snapshot, onRegenerate, isRegenerating }) {
  const brief = snapshot?.brief;
  if (!brief) return null;

  const briefMode = snapshot?.brief_mode || 'DISCOVERY';
  const createdAt = snapshot?.created_at;

  return (
    <Box>
      {/* Header */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ mb: 2 }}
      >
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="h5">Tactical Brief</Typography>
          <Chip
            label={briefMode}
            color={MODE_COLORS[briefMode] || 'default'}
            size="small"
          />
        </Stack>
        <Button
          variant="outlined"
          size="small"
          onClick={onRegenerate}
          disabled={isRegenerating}
          startIcon={
            isRegenerating
              ? <CircularProgress size={14} color="inherit" />
              : <SyncOutlined />
          }
        >
          {isRegenerating ? 'Regenerating…' : 'Regenerate'}
        </Button>
      </Stack>

      <Divider sx={{ mb: 2 }} />

      {/* Context */}
      {brief.context && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>
            Context
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {brief.context}
          </Typography>
        </Box>
      )}

      {/* Objectives — [{rank, summary, nature, success_criteria}] */}
      {brief.objectives?.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>
            Objectives
          </Typography>
          {brief.objectives.map((obj, idx) => (
            <Box key={idx} sx={{ mb: 2 }}>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
                <Chip
                  label={obj.rank?.toUpperCase()}
                  size="small"
                  color={obj.rank === 'primary' ? 'primary' : 'default'}
                />
                <Chip label={obj.nature} size="small" variant="outlined" />
              </Stack>
              <Typography variant="body2">{obj.summary}</Typography>
              {obj.success_criteria && (
                <Typography variant="caption" color="text.secondary">
                  Success: {obj.success_criteria}
                </Typography>
              )}
            </Box>
          ))}
        </Box>
      )}

      {/* Rhetoric — {register, key_argument, tangible_reformulation, proof} */}
      {brief.rhetoric && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>
            Rhetoric
          </Typography>
          <Stack spacing={1}>
            <Typography variant="body2">
              <strong>Register:</strong> {brief.rhetoric.register}
            </Typography>
            <Typography variant="body2">
              <strong>Key argument:</strong> {brief.rhetoric.key_argument}
            </Typography>
            <Typography variant="body2">
              <strong>Tangible reformulation:</strong> {brief.rhetoric.tangible_reformulation}
            </Typography>
            <Typography variant="body2">
              <strong>Proof:</strong> {brief.rhetoric.proof}
            </Typography>
          </Stack>
        </Box>
      )}

      {/* Gaps — [{topic, strategy, question}] */}
      {brief.gaps?.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>
            Discovery Gaps
          </Typography>
          {brief.gaps.map((gap, idx) => (
            <Box key={idx} sx={{ mb: 1.5 }}>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
                <Typography variant="body2" fontWeight={600}>{gap.topic}</Typography>
                <Chip
                  label={gap.strategy}
                  size="small"
                  color={gap.strategy === 'DIRECT' ? 'warning' : 'info'}
                  variant="outlined"
                />
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                &ldquo;{gap.question}&rdquo;
              </Typography>
            </Box>
          ))}
        </Box>
      )}

      {/* Next Step — {what, with_whom, when} */}
      {brief.next_step && (
        <Box sx={{ mb: 3, p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>
            Suggested Next Step
          </Typography>
          <Typography variant="body2">
            <strong>What:</strong> {brief.next_step.what}
          </Typography>
          <Typography variant="body2">
            <strong>With whom:</strong> {brief.next_step.with_whom}
          </Typography>
          <Typography variant="body2">
            <strong>When:</strong> {brief.next_step.when}
          </Typography>
        </Box>
      )}

      {/* Footer — snapshot date */}
      {createdAt && (
        <>
          <Divider sx={{ mt: 2, mb: 1 }} />
          <Typography variant="caption" color="text.disabled">
            Generated {new Date(createdAt).toLocaleString()}
          </Typography>
        </>
      )}
    </Box>
  );
}

PrepCallBrief.propTypes = {
  snapshot: PropTypes.shape({
    brief_mode: PropTypes.string,
    brief: PropTypes.shape({
      context: PropTypes.string,
      objectives: PropTypes.arrayOf(PropTypes.shape({
        rank: PropTypes.string,
        summary: PropTypes.string,
        nature: PropTypes.string,
        success_criteria: PropTypes.string,
      })),
      rhetoric: PropTypes.shape({
        register: PropTypes.string,
        key_argument: PropTypes.string,
        tangible_reformulation: PropTypes.string,
        proof: PropTypes.string,
      }),
      gaps: PropTypes.arrayOf(PropTypes.shape({
        topic: PropTypes.string,
        strategy: PropTypes.string,
        question: PropTypes.string,
      })),
      next_step: PropTypes.shape({
        what: PropTypes.string,
        with_whom: PropTypes.string,
        when: PropTypes.string,
      }),
    }),
    created_at: PropTypes.string,
  }).isRequired,
  onRegenerate: PropTypes.func.isRequired,
  isRegenerating: PropTypes.bool.isRequired,
};
