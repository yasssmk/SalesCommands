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
import IconButton from '@mui/material/IconButton';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

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
  onApply,
  onClear,
  hasPendingChanges,
  matchingCount = 0,
  loading = false
}) {
  
  // Fetch choices from backend
  const { types = [], classifications = [], choicesLoading } = useGetAccountChoices();

  // ==============================|| HANDLERS ||============================== //

  const handleTypeChange = (event) => {
    onFilterChange('type', event.target.value);
  };

  const handleClassificationChange = (event) => {
    onFilterChange('classification', event.target.value);
  };

  const handleOwnerChange = (user) => {
    onFilterChange('account_owner', user?.id || '');
  };

  const handleApply = () => {
    onApply?.();
    onClose?.();
  };

  const handleClear = () => {
    onClear?.();
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
            <FormControl fullWidth size="small">
              <InputLabel id="filter-type-label">Type</InputLabel>
              <Select
                labelId="filter-type-label"
                id="filter-type"
                value={pendingFilters?.type || ''}
                label="Type"
                onChange={handleTypeChange}
                disabled={choicesLoading}
              >
                <MenuItem value="">
                  <em>All types</em>
                </MenuItem>
                {types.map((type) => (
                  <MenuItem key={type.value} value={type.value}>
                    {type.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {/* Classification Filter */}
            <FormControl fullWidth size="small">
              <InputLabel id="filter-classification-label">Classification</InputLabel>
              <Select
                labelId="filter-classification-label"
                id="filter-classification"
                value={pendingFilters?.classification || ''}
                label="Classification"
                onChange={handleClassificationChange}
                disabled={choicesLoading}
              >
                <MenuItem value="">
                  <em>All classifications</em>
                </MenuItem>
                {classifications.map((classification) => (
                  <MenuItem key={classification.value} value={classification.value}>
                    {classification.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {/* Owner Filter */}
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
                Account Owner
              </Typography>
              <AsyncUserSelect
                value={pendingFilters?.account_owner ? { id: pendingFilters.account_owner } : null}
                onChange={handleOwnerChange}
                placeholder="All owners"
                size="small"
              />
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

          {/* Save as Territory - disabled for Phase 1 */}
          <Button
            fullWidth
            variant="outlined"
            startIcon={<SaveOutlined />}
            disabled
          >
            Save as Territory
          </Button>
          <Typography variant="caption" color="text.secondary" textAlign="center">
            Territory creation coming soon
          </Typography>
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
    type: PropTypes.string,
    classification: PropTypes.string,
    account_owner: PropTypes.string
  }),
  onFilterChange: PropTypes.func.isRequired,
  onApply: PropTypes.func.isRequired,
  onClear: PropTypes.func.isRequired,
  hasPendingChanges: PropTypes.bool,
  matchingCount: PropTypes.number,
  loading: PropTypes.bool
};