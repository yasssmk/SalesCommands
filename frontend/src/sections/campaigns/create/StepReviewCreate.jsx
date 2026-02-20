// frontend/src/sections/campaigns/create/StepReviewCreate.jsx
/**
 * Campaign Create Wizard — Step 3: Review & Create
 *
 * Read-only summary of all wizard data grouped by section.
 * User reviews before clicking "Create Campaign" in the footer.
 */

'use client';

import PropTypes from 'prop-types';

// material-ui
import { alpha, useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// api
import {
  CAMPAIGN_FAMILIES,
  CAMPAIGN_FAMILY_LABELS,
  SEQUENCE_TYPE_LABELS,
  OBJECTIVE_TYPE_LABELS
} from 'api/campaigns/campaigns';

// icons
import AimOutlined from '@ant-design/icons/AimOutlined';
import ThunderboltOutlined from '@ant-design/icons/ThunderboltOutlined';
import CalendarOutlined from '@ant-design/icons/CalendarOutlined';
import TrophyOutlined from '@ant-design/icons/TrophyOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import GlobalOutlined from '@ant-design/icons/GlobalOutlined';
import BankOutlined from '@ant-design/icons/BankOutlined';

// ==============================|| REVIEW ROW ||============================== //

/**
 * Single label → value row in the review summary
 */
function ReviewRow({ label, value, muted = false }) {
  return (
    <Stack direction="row" justifyContent="space-between" alignItems="flex-start" sx={{ py: 0.75 }}>
      <Typography variant="body2" color="text.secondary" sx={{ minWidth: 140, flexShrink: 0 }}>
        {label}
      </Typography>
      <Typography
        variant="body2"
        color={muted ? 'text.disabled' : 'text.primary'}
        fontStyle={muted ? 'italic' : 'normal'}
        sx={{ textAlign: 'right' }}
      >
        {value}
      </Typography>
    </Stack>
  );
}

ReviewRow.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.node.isRequired,
  muted: PropTypes.bool
};

// ==============================|| REVIEW SECTION ||============================== //

/**
 * Grouped section with icon, title, and rows
 */
function ReviewSection({ icon, title, children }) {
  const theme = useTheme();

  return (
    <Box
      sx={{
        p: 2,
        borderRadius: 1.5,
        bgcolor: 'grey.50',
        border: '1px solid',
        borderColor: 'grey.200'
      }}
    >
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
        {icon}
        <Typography variant="subtitle2">{title}</Typography>
      </Stack>
      <Stack divider={<Divider flexItem />} spacing={0}>
        {children}
      </Stack>
    </Box>
  );
}

ReviewSection.propTypes = {
  icon: PropTypes.node,
  title: PropTypes.string.isRequired,
  children: PropTypes.node
};

// ==============================|| STEP REVIEW CREATE ||============================== //

export default function StepReviewCreate({ data }) {
  const theme = useTheme();
  const isProspection = data.family === CAMPAIGN_FAMILIES.PROSPECTION;

  // ==============================|| FORMAT HELPERS ||============================== //

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Not set';
    const d = new Date(dateStr);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const familyLabel = CAMPAIGN_FAMILY_LABELS[data.family] || data.family;
  const sequenceLabel = data.sequence_type ? SEQUENCE_TYPE_LABELS[data.sequence_type] : null;
  const objectiveLabel = data.objective_type ? OBJECTIVE_TYPE_LABELS[data.objective_type] : null;

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 1 }}>
        Review your campaign
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Verify the details below before creating the campaign.
      </Typography>

      <Stack spacing={2}>

        {/* ==================== TYPE & TARGET ==================== */}
        <ReviewSection
          icon={
            isProspection
              ? <AimOutlined style={{ fontSize: 18, color: theme.palette.primary.main }} />
              : <ThunderboltOutlined style={{ fontSize: 18, color: theme.palette.warning.main }} />
          }
          title="Type & Target"
        >
          <ReviewRow label="Family" value={
            <Chip
              label={familyLabel}
              size="small"
              color={isProspection ? 'primary' : 'warning'}
              variant="outlined"
            />
          } />

          {isProspection ? (
            <ReviewRow
              label="Territory"
              value={
                data.territory_name ? (
                  <Stack direction="row" spacing={0.5} alignItems="center">
                    <GlobalOutlined style={{ fontSize: 14, color: theme.palette.text.secondary }} />
                    <span>{data.territory_name}</span>
                  </Stack>
                ) : 'Not selected'
              }
              muted={!data.territory_name}
            />
          ) : (
            <ReviewRow
              label="Accounts"
              value={
                (data.selectedAccounts || []).length > 0 ? (
                  <Stack direction="row" spacing={0.5} alignItems="center" flexWrap="wrap" justifyContent="flex-end" useFlexGap>
                    {data.selectedAccounts.slice(0, 3).map((a) => (
                      <Chip
                        key={a.id}
                        label={a.company_name || a.id}
                        size="small"
                        variant="outlined"
                        icon={<BankOutlined style={{ fontSize: 12 }} />}
                      />
                    ))}
                    {data.selectedAccounts.length > 3 && (
                      <Typography variant="caption" color="text.secondary">
                        +{data.selectedAccounts.length - 3} more
                      </Typography>
                    )}
                  </Stack>
                ) : 'None selected'
              }
              muted={!(data.selectedAccounts || []).length}
            />
          )}

          {isProspection && sequenceLabel && (
            <ReviewRow label="Sequence" value={sequenceLabel} />
          )}
        </ReviewSection>

        {/* ==================== DETAILS ==================== */}
        <ReviewSection
          icon={<CalendarOutlined style={{ fontSize: 18, color: theme.palette.info.main }} />}
          title="Details"
        >
          <ReviewRow label="Name" value={data.name || 'Untitled'} muted={!data.name} />
          <ReviewRow
            label="Description"
            value={data.description || 'No description'}
            muted={!data.description}
          />
          <ReviewRow label="Start Date" value={formatDate(data.start_date)} muted={!data.start_date} />
          <ReviewRow label="End Date" value={formatDate(data.end_date)} muted={!data.end_date} />
        </ReviewSection>

        {/* ==================== OBJECTIVE ==================== */}
        <ReviewSection
          icon={<TrophyOutlined style={{ fontSize: 18, color: theme.palette.success.main }} />}
          title="Objective"
        >
          {objectiveLabel ? (
            <>
              <ReviewRow label="Type" value={objectiveLabel} />
              <ReviewRow
                label="Target"
                value={data.objective_target || 'Not set'}
                muted={!data.objective_target}
              />
            </>
          ) : (
            <ReviewRow label="Objective" value="No objective set" muted />
          )}
        </ReviewSection>

        {/* ==================== TEAM ==================== */}
        <ReviewSection
          icon={<TeamOutlined style={{ fontSize: 18, color: theme.palette.secondary.main }} />}
          title="Team"
        >
          <ReviewRow label="Owner" value="You (current user)" />
          <ReviewRow
            label="Executors"
            value={
              (data.selectedExecutors || []).length > 0
                ? data.selectedExecutors.map((u) =>
                    `${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email
                  ).join(', ')
                : 'None'
            }
            muted={!(data.selectedExecutors || []).length}
          />
        </ReviewSection>

      </Stack>
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

StepReviewCreate.propTypes = {
  /** Full wizard data object */
  data: PropTypes.object.isRequired
};