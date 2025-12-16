// frontend/src/sections/territories/TerritoryFilterPanel.jsx

import PropTypes from 'prop-types';
import { useState } from 'react';

// material-ui
import Accordion from '@mui/material/Accordion';
import AccordionDetails from '@mui/material/AccordionDetails';
import AccordionSummary from '@mui/material/AccordionSummary';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Divider from '@mui/material/Divider';
import Drawer from '@mui/material/Drawer';
import FormControl from '@mui/material/FormControl';
import FormControlLabel from '@mui/material/FormControlLabel';
import IconButton from '@mui/material/IconButton';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import MultiSelectFilter from 'components/filters/MultiSelectFilter';

// next
import { useRouter } from 'next/navigation';

// icons
import CloseOutlined from '@ant-design/icons/CloseOutlined';
import DownOutlined from '@ant-design/icons/DownOutlined';
import FilterOutlined from '@ant-design/icons/FilterOutlined';
import SaveOutlined from '@ant-design/icons/SaveOutlined';
import ClearOutlined from '@ant-design/icons/ClearOutlined';

// project imports
import AsyncUserSelect from 'components/AsyncSelection/AsyncUserSelect';

// api
import { useGetAccountChoices } from 'api/admin/accounts';

// ==============================|| FILTER SECTION COMPONENT ||============================== //

/**
 * Reusable accordion section for filter groups
 */
function FilterSection({ title, icon, defaultExpanded = true, children }) {
  return (
    <Accordion defaultExpanded={defaultExpanded} disableGutters elevation={0}>
      <AccordionSummary
        expandIcon={<DownOutlined />}
        sx={{
          bgcolor: 'grey.50',
          '&:hover': { bgcolor: 'grey.100' },
          minHeight: 48,
          '& .MuiAccordionSummary-content': { my: 1 }
        }}
      >
        <Stack direction="row" spacing={1} alignItems="center">
          {icon}
          <Typography variant="subtitle2">{title}</Typography>
        </Stack>
      </AccordionSummary>
      <AccordionDetails sx={{ pt: 2, pb: 3 }}>
        {children}
      </AccordionDetails>
    </Accordion>
  );
}

FilterSection.propTypes = {
  title: PropTypes.string.isRequired,
  icon: PropTypes.node,
  defaultExpanded: PropTypes.bool,
  children: PropTypes.node
};

// ==============================|| TERRITORY FILTER PANEL ||============================== //

/**
 * Slide-in drawer for territory filters
 * 
 * Phase 1: Basic filters (Type, Classification, Owner)
 * Future: Add more filter sections (TechStack, Qualification, etc.)
 */
export default function TerritoryFilterPanel({
  open,
  onClose,
  pendingFilters,
  onFilterChange,
  onFiltersChange,
  onApply,
  onClear,
  hasPendingChanges,
  matchingCount = 0,
  loading = false
}) {
  
  const router = useRouter();
  
  // Fetch choices from backend
  const { types = [], classifications = [], choicesLoading } = useGetAccountChoices();

  // ==============================|| HANDLERS ||============================== //

  const handleTypeChange = (newValues) => {
    onFilterChange('type', newValues);
  };

  const handleClassificationChange = (newValues) => {
    onFilterChange('classification', newValues);
  };

  /**
  * Handle owner scope radio change
  */
  const handleOwnerScopeChange = (event) => {
    const newScope = event.target.value;
    onFilterChange('account_scope', newScope);
    
    // Clear account_owner when switching away from 'other'
    if (newScope !== 'other') {
      onFilterChange('account_owner', null);
    }
  };

  /**
   * Handle specific user selection (when scope is 'other')
   */
  const handleOwnerUserChange = (event, user) => {
    onFilterChange('account_owner', user || null);
  };

  /**
   * Get current scope value for radio buttons
   * Returns 'other' if a specific user is selected
   */
  const getCurrentScope = () => {
    if (pendingFilters?.account_owner?.id) {
      return 'other';
    }
    return pendingFilters?.account_scope || '';
  };

  const handleApply = () => {
    onApply?.();
    onClose?.();
  };

  const handleClear = () => {
    onClear?.();
  };

  const handleSaveAsTerritory = () => {
    // Build query params from pending filters
    const params = new URLSearchParams();
    params.set('action', 'create');
    
    // Handle array filters (join with comma for URL)
    if (pendingFilters?.type?.length > 0) {
      params.set('filter_type', pendingFilters.type.join(','));
    }
    if (pendingFilters?.classification?.length > 0) {
      params.set('filter_classification', pendingFilters.classification.join(','));
    }
    // Account scope (mine/team)
    if (pendingFilters?.account_scope) {
      params.set('filter_account_scope', pendingFilters.account_scope);
    }
    // Account owner (specific user) - only if no scope set
    if (!pendingFilters?.account_scope && pendingFilters?.account_owner?.id) {
      params.set('filter_owner', pendingFilters.account_owner.id);
    }
    
    // Close drawer and navigate
    onClose?.();
    router.push(`/territories?${params.toString()}`);
  };

  // ==============================|| RENDER ||============================== //

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: { width: { xs: '100%', sm: 400 } }
      }}
    >
      {/* ==================== HEADER ==================== */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}
      >
        <Stack direction="row" spacing={1} alignItems="center">
          <FilterOutlined style={{ fontSize: 20 }} />
          <Typography variant="h5">Filters</Typography>
        </Stack>
        <IconButton onClick={onClose} size="small">
          <CloseOutlined />
        </IconButton>
      </Stack>

      {/* ==================== FILTER SECTIONS ==================== */}
      <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
        
        {/* Account Profile Filters */}
        <FilterSection 
          title="Account Profile" 
          icon={<FilterOutlined style={{ fontSize: 16, color: '#8c8c8c' }} />}
          defaultExpanded={true}
        >
          <Stack spacing={2.5}>
            
            {/* Type Filter */}
            <MultiSelectFilter
              label="Type"
              options={types}
              value={pendingFilters?.type || []}
              onChange={handleTypeChange}
              placeholder="All types"
              loading={choicesLoading}
              size="small"
            />

            {/* Classification Filter */}
            <MultiSelectFilter
              label="Classification"
              options={classifications}
              value={pendingFilters?.classification || []}
              onChange={handleClassificationChange}
              placeholder="All classifications"
              loading={choicesLoading}
              size="small"
            />

            {/* Owner Scope Filter */}
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
                Account Owner
              </Typography>
              <FormControl component="fieldset" fullWidth>
                <RadioGroup
                  value={getCurrentScope()}
                  onChange={handleOwnerScopeChange}
                  sx={{ gap: 0.5 }}
                >
                  <FormControlLabel 
                    value="" 
                    control={<Radio size="small" />} 
                    label="All" 
                    sx={{ '& .MuiFormControlLabel-label': { fontSize: '0.875rem' } }}
                  />
                  <FormControlLabel 
                    value="mine" 
                    control={<Radio size="small" />} 
                    label="Mine" 
                    sx={{ '& .MuiFormControlLabel-label': { fontSize: '0.875rem' } }}
                  />
                  <FormControlLabel 
                    value="team" 
                    control={<Radio size="small" />} 
                    label="My Team" 
                    sx={{ '& .MuiFormControlLabel-label': { fontSize: '0.875rem' } }}
                  />
                  <FormControlLabel 
                    value="other" 
                    control={<Radio size="small" />} 
                    label="Specific user" 
                    sx={{ '& .MuiFormControlLabel-label': { fontSize: '0.875rem' } }}
                  />
                </RadioGroup>
              </FormControl>
              
              {/* User Select - only enabled when 'other' is selected */}
              <Box sx={{ mt: 1.5, pl: 3.5 }}>
                <AsyncUserSelect
                  value={pendingFilters?.account_owner || null}
                  onChange={handleOwnerUserChange}
                  placeholder="Select user..."
                  size="small"
                  disabled={getCurrentScope() !== 'other'}
                />
              </Box>
            </Box>

          </Stack>
        </FilterSection>

        {/* Future sections - disabled for Phase 1 */}
        <FilterSection 
          title="Qualification" 
          icon={<FilterOutlined style={{ fontSize: 16, color: '#8c8c8c' }} />}
          defaultExpanded={false}
        >
          <Typography variant="body2" color="text.secondary">
            Qualification filters coming soon.
          </Typography>
        </FilterSection>

        <FilterSection 
          title="Tech Stack" 
          icon={<FilterOutlined style={{ fontSize: 16, color: '#8c8c8c' }} />}
          defaultExpanded={false}
        >
          <Typography variant="body2" color="text.secondary">
            Tech stack filters coming soon.
          </Typography>
        </FilterSection>

        <FilterSection 
          title="Engagement" 
          icon={<FilterOutlined style={{ fontSize: 16, color: '#8c8c8c' }} />}
          defaultExpanded={false}
        >
          <Typography variant="body2" color="text.secondary">
            Engagement filters coming soon.
          </Typography>
        </FilterSection>

      </Box>

      {/* ==================== FOOTER ==================== */}
      <Box sx={{ borderTop: 1, borderColor: 'divider', p: 2 }}>
        
        {/* Matching count */}
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
          <Typography variant="body2" color="text.secondary">
            Matching:
          </Typography>
          <Typography variant="subtitle1" fontWeight={600}>
            {loading ? '...' : `${matchingCount} accounts`}
          </Typography>
        </Stack>

        {/* Action buttons */}
        <Stack spacing={1.5}>
          <Stack direction="row" spacing={1}>
            <Button
              fullWidth
              variant="outlined"
              color="secondary"
              startIcon={<ClearOutlined />}
              onClick={handleClear}
            >
              Clear all
            </Button>
            <Button
              fullWidth
              variant="contained"
              onClick={handleApply}
              disabled={!hasPendingChanges}
            >
              Apply
            </Button>
          </Stack>

          <Divider sx={{ my: 1 }}>
            <Typography variant="caption" color="text.secondary">or</Typography>
          </Divider>

          {/* Save as Territory */}
          <Button
            fullWidth
            variant="outlined"
            startIcon={<SaveOutlined />}
            onClick={handleSaveAsTerritory}
          >
            Save as Territory
          </Button>
        </Stack>
      </Box>
    </Drawer>
  );
}

// ==============================|| PROP TYPES ||============================== //

TerritoryFilterPanel.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  pendingFilters: PropTypes.shape({
    type: PropTypes.arrayOf(PropTypes.string),
    classification: PropTypes.arrayOf(PropTypes.string),
    account_scope: PropTypes.string,
    account_owner: PropTypes.oneOfType([PropTypes.object, PropTypes.string])
  }),
  onFilterChange: PropTypes.func.isRequired,
  onFiltersChange: PropTypes.func,
  onApply: PropTypes.func.isRequired,
  onClear: PropTypes.func.isRequired,
  hasPendingChanges: PropTypes.bool,
  matchingCount: PropTypes.number,
  loading: PropTypes.bool
};