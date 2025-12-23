// frontend/src/sections/territories/workspace/TerritoryHeader.jsx

'use client';

import PropTypes from 'prop-types';

// material-ui
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project imports
import MainCard from 'components/MainCard';
import { TERRITORY_TYPES } from 'api/territories/territories';

// assets
import BankOutlined from '@ant-design/icons/BankOutlined';
import ContactsOutlined from '@ant-design/icons/ContactsOutlined';
import FilterOutlined from '@ant-design/icons/FilterOutlined';

// ==============================|| TERRITORY HEADER - LOADING ||============================== //

function TerritoryHeaderSkeleton() {
  return (
    <MainCard sx={{ mb: 2 }}>
      <Stack spacing={2}>
        {/* Name row skeleton */}
        <Stack direction="row" alignItems="center" spacing={2}>
          <Skeleton variant="text" width={280} height={40} />
          <Skeleton variant="rectangular" width={80} height={24} sx={{ borderRadius: 4 }} />
        </Stack>

        {/* Description skeleton */}
        <Skeleton variant="text" width="60%" height={20} />

        {/* Filters skeleton */}
        <Stack direction="row" spacing={1}>
          <Skeleton variant="rectangular" width={100} height={24} sx={{ borderRadius: 4 }} />
          <Skeleton variant="rectangular" width={120} height={24} sx={{ borderRadius: 4 }} />
          <Skeleton variant="rectangular" width={90} height={24} sx={{ borderRadius: 4 }} />
        </Stack>

        {/* Stats skeleton */}
        <Stack direction="row" spacing={3} pt={1}>
          <Skeleton variant="text" width={80} height={20} />
          <Skeleton variant="text" width={80} height={20} />
        </Stack>
      </Stack>
    </MainCard>
  );
}

// ==============================|| FILTER CHIP ||============================== //

/**
 * Display a filter as a chip
 */
function FilterChip({ label, value }) {
  if (!value) return null;
  
  const displayValue = Array.isArray(value) 
    ? (value.length === 1 ? value[0] : `${value.length} selected`)
    : value;

  return (
    <Chip
      size="small"
      variant="outlined"
      label={`${label}: ${displayValue}`}
      sx={{ borderRadius: 1 }}
    />
  );
}

FilterChip.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.array])
};

// ==============================|| TERRITORY HEADER ||============================== //

/**
 * Territory Header Component
 * 
 * Displays territory information in the workspace header:
 * - Territory name
 * - Type badge (Account/Contact)
 * - System badge (if applicable)
 * - Description
 * - Applied filters summary
 * - Stats summary
 */
export default function TerritoryHeader({ territory, stats, loading }) {
  // ==============================|| LOADING STATE ||============================== //

  if (loading) {
    return <TerritoryHeaderSkeleton />;
  }

  // ==============================|| NO DATA STATE ||============================== //

  if (!territory) {
    return null;
  }

  // ==============================|| DERIVED VALUES ||============================== //

  const isAccountType = territory.type === TERRITORY_TYPES.ACCOUNT;
  const TypeIcon = isAccountType ? BankOutlined : ContactsOutlined;
  const typeLabel = isAccountType ? 'Accounts' : 'Contacts';
  const typeColor = isAccountType ? 'primary' : 'secondary';

  // ==============================|| FILTER SUMMARY ||============================== //

  const filters = territory.filter_definition || {};
  const hasFilters = Object.keys(filters).length > 0;

  const scopeLabels = {
    mine: 'Mine',
    team: 'My Team',
    all: 'All'
  };

  // ==============================|| RENDER ||============================== //

  return (
    <MainCard sx={{ mb: 2 }}>
      <Stack spacing={2}>
        {/* Row 1: Name, Type Badge, System Badge */}
        <Stack
          direction="row"
          alignItems="center"
          spacing={2}
          sx={{ flexWrap: 'wrap' }}
        >
          {/* Territory Name */}
          <Typography variant="h3" component="h1" sx={{ flexGrow: 1 }}>
            {territory.name}
          </Typography>

          {/* Type Badge */}
          <Chip
            icon={<TypeIcon style={{ fontSize: 14 }} />}
            label={typeLabel}
            color={typeColor}
            size="small"
            variant="outlined"
          />

          {/* System Badge */}
          {territory.is_system && (
            <Chip
              label="System"
              color="default"
              size="small"
              variant="filled"
            />
          )}
        </Stack>

        {/* Row 2: Description */}
        {territory.description && (
          <Typography variant="body1" color="text.secondary">
            {territory.description}
          </Typography>
        )}

        {/* Row 3: Applied Filters */}
        <Box>
          <Stack direction="row" spacing={0.5} alignItems="center" mb={1}>
            <FilterOutlined style={{ fontSize: 14, color: 'inherit' }} />
            <Typography variant="body2" color="text.secondary" fontWeight={500}>
              Filters
            </Typography>
          </Stack>
          
          {hasFilters ? (
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <FilterChip label="Type" value={filters.type} />
              <FilterChip label="Classification" value={filters.classification} />
              <FilterChip label="Industry" value={filters.industry} />
              <FilterChip label="Country" value={filters.country} />
              {filters.account_scope && (
                <Chip
                  size="small"
                  variant="outlined"
                  label={`Owner: ${scopeLabels[filters.account_scope] || filters.account_scope}`}
                  sx={{ borderRadius: 1 }}
                />
              )}
              {filters.account_owner && (
                <Chip
                  size="small"
                  variant="outlined"
                  label="Owner: Specific user"
                  sx={{ borderRadius: 1 }}
                />
              )}
            </Stack>
          ) : (
            <Typography variant="body2" color="text.secondary" fontStyle="italic">
              No filters applied — includes all {typeLabel.toLowerCase()}
            </Typography>
          )}
        </Box>

        {/* Row 4: Stats Summary */}
        {stats && (
          <Box
            sx={{
              pt: 1,
              borderTop: 1,
              borderColor: 'divider'
            }}
          >
            <Stack
              direction="row"
              spacing={{ xs: 2, sm: 4 }}
              flexWrap="wrap"
              useFlexGap
            >
              <StatItem label="Accounts" value={stats.accounts_count} />
              <StatItem label="Contacts" value={stats.contacts_count} />
              <StatItem label="Activities" value={stats.activities_count} />
            </Stack>
          </Box>
        )}
      </Stack>
    </MainCard>
  );
}

// ==============================|| STAT ITEM ||============================== //

function StatItem({ label, value }) {
  return (
    <Stack direction="row" spacing={0.5} alignItems="baseline">
      <Typography variant="h6" component="span">
        {value ?? 0}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
    </Stack>
  );
}

// ==============================|| PROP TYPES ||============================== //

TerritoryHeader.propTypes = {
  territory: PropTypes.shape({
    id: PropTypes.string,
    name: PropTypes.string,
    description: PropTypes.string,
    type: PropTypes.oneOf(['ACCOUNT', 'CONTACT']),
    is_system: PropTypes.bool,
    filter_definition: PropTypes.object
  }),
  stats: PropTypes.shape({
    accounts_count: PropTypes.number,
    contacts_count: PropTypes.number,
    activities_count: PropTypes.number
  }),
  loading: PropTypes.bool
};

StatItem.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.number
};