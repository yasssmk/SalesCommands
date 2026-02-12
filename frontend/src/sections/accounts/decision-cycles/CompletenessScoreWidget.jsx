// frontend/src/components/CompletenessScoreWidget.jsx
/**
 * Completeness Score Widget Component
 * 
 * Displays a step's documentation completeness score with visual indicator,
 * category badge, and actionable suggestions for improvement.
 * 
 * Used in:
 * - Step Detail Overview tab
 * - Activity Preparation tab (if step linked)
 * - Next step creation flow (future)
 */

'use client';

import PropTypes from 'prop-types';
import { useState } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useTheme } from '@mui/material/styles';

// ant-design icons
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';
import DownOutlined from '@ant-design/icons/DownOutlined';
import ExclamationCircleOutlined from '@ant-design/icons/ExclamationCircleOutlined';
import InfoCircleOutlined from '@ant-design/icons/InfoCircleOutlined';
import RightOutlined from '@ant-design/icons/RightOutlined';
import WarningOutlined from '@ant-design/icons/WarningOutlined';

// ==============================|| CONSTANTS ||============================== //

/**
 * Score category thresholds and styling
 */
const SCORE_CATEGORIES = {
  excellent: {
    min: 80,
    label: 'Excellent',
    color: 'success',
    icon: CheckCircleOutlined,
    message: 'Great documentation! You\'re well prepared.'
  },
  good: {
    min: 60,
    label: 'Good',
    color: 'info',
    icon: InfoCircleOutlined,
    message: 'Solid foundation. A few additions would strengthen your position.'
  },
  fair: {
    min: 40,
    label: 'Fair',
    color: 'warning',
    icon: WarningOutlined,
    message: 'Some key information is missing. Consider filling the gaps.'
  },
  poor: {
    min: 0,
    label: 'Needs Work',
    color: 'error',
    icon: ExclamationCircleOutlined,
    message: 'Important details are missing. Adding them will improve your preparation.'
  }
};

/**
 * Get category based on score
 */
const getScoreCategory = (score) => {
  if (score >= SCORE_CATEGORIES.excellent.min) return SCORE_CATEGORIES.excellent;
  if (score >= SCORE_CATEGORIES.good.min) return SCORE_CATEGORIES.good;
  if (score >= SCORE_CATEGORIES.fair.min) return SCORE_CATEGORIES.fair;
  return SCORE_CATEGORIES.poor;
};

/**
 * Get color for circular progress based on score
 */
const getProgressColor = (score, theme) => {
  if (score >= 80) return theme.palette.success.main;
  if (score >= 60) return theme.palette.info.main;
  if (score >= 40) return theme.palette.warning.main;
  return theme.palette.error.main;
};

// ==============================|| CIRCULAR SCORE DISPLAY ||============================== //

function CircularScoreDisplay({ score }) {
  const theme = useTheme();
  const progressColor = getProgressColor(score, theme);

  return (
    <Box sx={{ position: 'relative', display: 'inline-flex' }}>
      {/* Background circle */}
      <CircularProgress
        variant="determinate"
        value={100}
        size={72}
        thickness={4}
        sx={{ color: theme.palette.grey[200] }}
      />
      {/* Foreground progress */}
      <CircularProgress
        variant="determinate"
        value={score}
        size={72}
        thickness={4}
        sx={{
          position: 'absolute',
          left: 0,
          color: progressColor,
          '& .MuiCircularProgress-circle': {
            strokeLinecap: 'round'
          }
        }}
      />
      {/* Score text */}
      <Box
        sx={{
          position: 'absolute',
          top: 0,
          left: 0,
          bottom: 0,
          right: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}
      >
        <Typography variant="h4" fontWeight={theme.typography.fontWeightBold} color="text.primary">
          {score}
        </Typography>
      </Box>
    </Box>
  );
}

CircularScoreDisplay.propTypes = {
  score: PropTypes.number.isRequired
};

// ==============================|| SUGGESTIONS LIST ||============================== //

function SuggestionsList({ suggestions }) {
  const theme = useTheme();
  if (!suggestions || suggestions.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
        No specific suggestions at this time.
      </Typography>
    );
  }

  return (
    <List dense disablePadding>
      {suggestions.map((suggestion, index) => (
        <ListItem key={index} disablePadding sx={{ py: 0.5 }}>
          <ListItemIcon sx={{ minWidth: 28 }}>
            <RightOutlined style={{ fontSize: theme.iconSizes.xs, color: 'inherit' }} />
          </ListItemIcon>
          <ListItemText
            primary={suggestion}
            primaryTypographyProps={{
              variant: 'body2',
              color: 'text.secondary'
            }}
          />
        </ListItem>
      ))}
    </List>
  );
}

SuggestionsList.propTypes = {
  suggestions: PropTypes.arrayOf(PropTypes.string)
};

// ==============================|| COMPLETENESS SCORE WIDGET ||============================== //

/**
 * CompletenessScoreWidget Component
 * 
 * @param {number} score - Completeness score (0-100)
 * @param {string} category - Category from backend (optional, will be computed if not provided)
 * @param {string[]} suggestions - List of improvement suggestions
 * @param {string} variant - Display variant: 'full' (with suggestions) or 'compact' (score only)
 * @param {boolean} defaultExpanded - Whether suggestions are expanded by default
 * @param {string} title - Optional custom title
 */
export default function CompletenessScoreWidget({
  score = 0,
  category: categoryOverride,
  suggestions = [],
  variant = 'full',
  defaultExpanded = false,
  title = 'Documentation Readiness'
}) {
  const theme = useTheme();
  const [expanded, setExpanded] = useState(defaultExpanded);
  
  // Compute category from score or use override
  const category = categoryOverride 
    ? SCORE_CATEGORIES[categoryOverride.toLowerCase()] || getScoreCategory(score)
    : getScoreCategory(score);
  
  const CategoryIcon = category.icon;
  const hasSuggestions = suggestions && suggestions.length > 0;

  // ==============================|| COMPACT VARIANT ||============================== //

  if (variant === 'compact') {
    return (
      <Stack direction="row" alignItems="center" spacing={1.5}>
        <Box sx={{ position: 'relative', display: 'inline-flex' }}>
          <CircularProgress
            variant="determinate"
            value={score}
            size={40}
            thickness={4}
            color={category.color}
          />
          <Box
            sx={{
              position: 'absolute',
              top: 0,
              left: 0,
              bottom: 0,
              right: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            <Typography variant="caption" fontWeight={theme.typography.fontWeightBold}>
              {score}
            </Typography>
          </Box>
        </Box>
        <Chip
          size="small"
          label={category.label}
          color={category.color}
          variant="outlined"
        />
      </Stack>
    );
  }

  // ==============================|| FULL VARIANT ||============================== //

  return (
    <Card variant="outlined" sx={{ borderRadius: 2 }}>
      <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
        {/* Header */}
        <Stack direction="row" alignItems="flex-start" spacing={2.5}>
          {/* Circular Score */}
          <CircularScoreDisplay score={score} />
          
          {/* Text Content */}
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.5 }}>
              <Typography variant="subtitle1" fontWeight={theme.typography.fontWeightBold}>
                {title}
              </Typography>
              <Chip
                size="small"
                label={category.label}
                color={category.color}
                icon={<CategoryIcon style={{ fontSize: theme.iconSizes.sm }} />}
              />
            </Stack>
            
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {category.message}
            </Typography>
            
            {/* Suggestions Toggle (only if has suggestions) */}
            {hasSuggestions && (
              <Stack
                direction="row"
                alignItems="center"
                spacing={0.5}
                onClick={() => setExpanded(!expanded)}
                sx={{
                  cursor: 'pointer',
                  color: 'primary.main',
                  '&:hover': { textDecoration: 'underline' }
                }}
              >
                <Typography variant="body2" fontWeight={theme.typography.fontWeightMedium}>
                  {expanded ? 'Hide suggestions' : `View ${suggestions.length} suggestion${suggestions.length > 1 ? 's' : ''}`}
                </Typography>
                <IconButton size="small" sx={{ p: 0 }}>
                  {expanded ? (
                    <DownOutlined style={{ fontSize: theme.iconSizes.xs }} />
                  ) : (
                    <RightOutlined style={{ fontSize: theme.iconSizes.xs }} />
                  )}
                </IconButton>
              </Stack>
            )}
          </Box>
        </Stack>
        
        {/* Collapsible Suggestions */}
        {hasSuggestions && (
          <Collapse in={expanded}>
            <Box sx={{ mt: 2, pt: 2, borderTop: 1, borderColor: 'divider' }}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                How to improve:
              </Typography>
              <SuggestionsList suggestions={suggestions} />
            </Box>
          </Collapse>
        )}
      </CardContent>
    </Card>
  );
}

// ==============================|| PROP TYPES ||============================== //

CompletenessScoreWidget.propTypes = {
  score: PropTypes.number,
  category: PropTypes.oneOf(['excellent', 'good', 'fair', 'poor', 'EXCELLENT', 'GOOD', 'FAIR', 'POOR']),
  suggestions: PropTypes.arrayOf(PropTypes.string),
  variant: PropTypes.oneOf(['full', 'compact']),
  defaultExpanded: PropTypes.bool,
  title: PropTypes.string
};

// ==============================|| EXPORTS ||============================== //

export { SCORE_CATEGORIES, getScoreCategory };
