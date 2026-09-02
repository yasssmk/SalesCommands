// frontend/src/views/territories/list.jsx

'use client';

import { useState, useMemo, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';

// material-ui
import useMediaQuery from '@mui/material/useMediaQuery';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
import Chip from '@mui/material/Chip';
import Badge from '@mui/material/Badge';
import IconButton from '@mui/material/IconButton';
import Grid from '@mui/material/Grid';
import Pagination from '@mui/material/Pagination';
import Slide from '@mui/material/Slide';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import Dialog from '@mui/material/Dialog';

// project imports
import MainCard from 'components/MainCard';
import { DebouncedInput } from 'components/third-party/react-table';
import TerritoryCard from 'sections/territories/TerritoryCard';
import TerritoryModal from 'sections/territories/TerritoryModal';
import AlertTerritoryDelete from 'sections/territories/AlertTerritoryDelete';
import AlertTerritoryBulkDelete from 'sections/territories/AlertTerritoryBulkDelete';
import TerritoryListFilterPanel from 'sections/territories/TerritoryListFilterPanel';

// hooks
import { useBreadcrumb } from 'contexts/BreadcrumbContext';
import useTerritoryListFilters from 'hooks/useTerritoryListFilters';

// Static section trail for the layout BreadcrumbBar (stable ref → no effect loop).
const TERRITORIES_CRUMBS = [{ label: 'Territories' }];

// api
import { useGetTerritories, useGetTerritoryCounts } from 'api/territories/territories';

// assets
import PlusOutlined from '@ant-design/icons/PlusOutlined';
import FilterOutlined from '@ant-design/icons/FilterOutlined';
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';
import CheckSquareOutlined from '@ant-design/icons/CheckSquareOutlined';
import CloseOutlined from '@ant-design/icons/CloseOutlined';

// ==============================|| TERRITORIES LIST PAGE ||============================== //

/**
 * Territories Page - Sales-facing workspace
 * 
 * Displays territories as cards for easy navigation.
 * Each card shows count and allows exploring accounts.
 * 
 * Phase 1: Hardcoded territories (All Accounts, All Contacts)
 * Future: Backend API for territory CRUD
 */
export default function TerritoriesListPage() {
  const matchDownSM = useMediaQuery((theme) => theme.breakpoints.down('sm'));

  // Declare this section's trail to the layout BreadcrumbBar.
  const { setCrumbs } = useBreadcrumb();
  useEffect(() => {
    setCrumbs(TERRITORIES_CRUMBS);
    return () => setCrumbs([]);
  }, [setCrumbs]);

  // ==============================|| STATE ||============================== //

  const [globalFilter, setGlobalFilter] = useState('');
  const [page, setPage] = useState(1);

  // URL params for pre-filled filters
const searchParams = useSearchParams();

// Modal states
const [addModalOpen, setAddModalOpen] = useState(false);
const [editModalOpen, setEditModalOpen] = useState(false);
const [deleteModalOpen, setDeleteModalOpen] = useState(false);
const [bulkDeleteModalOpen, setBulkDeleteModalOpen] = useState(false);
const [selectedTerritory, setSelectedTerritory] = useState(null);

// Selection states
const [selectedRows, setSelectedRows] = useState(new Set());
const [selectionMode, setSelectionMode] = useState(false);

// Initial filters from URL (for "Save as Territory" from filter panel)
const [initialFilters, setInitialFilters] = useState({});

// Filter drawer
const [filterPanelOpen, setFilterPanelOpen] = useState(false);
const {
  filters,
  pendingFilters,
  activeFiltersCount,
  hasPendingChanges,
  apiFilters,
  updatePendingFilter,
  applyFilters,
  clearFilters,
  resetPendingFilters,
  removeFilter
} = useTerritoryListFilters();

// Auto-open Add modal if action=create in URL
useEffect(() => {
  const action = searchParams.get('action');
  if (action === 'create') {
    // Extract filter params
    const filters = {};
    const filterType = searchParams.get('filter_type');
    const filterClassification = searchParams.get('filter_classification');
    const filterOwner = searchParams.get('filter_owner');
    
    if (filterType) filters.type = filterType;
    if (filterClassification) filters.classification = filterClassification;
    if (filterOwner) filters.account_owner = filterOwner;
    
    setInitialFilters(filters);
    setAddModalOpen(true);
    
    // Clean URL without reload
    window.history.replaceState({}, '', '/territories');
  }
}, [searchParams]);

  // ==============================|| PAGINATION CONFIG ||============================== //

  const PER_PAGE = 6;

  // ==============================|| API DATA - TERRITORIES ||============================== //

  const { 
  territories = [], 
  territoriesCount = 0, 
  territoriesLoading,
  territoriesError 
} = useGetTerritories({
  page: 1,
  pageSize: 100,
  search: globalFilter,
  filters: apiFilters
});

  // ==============================|| FILTERED TERRITORIES ||============================== //

  const filteredTerritories = useMemo(() => {
    return territories;
  }, [territories]);

  // ==============================|| PAGINATION ||============================== //

  const totalPages = Math.ceil(territoriesCount / PER_PAGE);

  const paginatedTerritories = useMemo(() => {
    const startIndex = (page - 1) * PER_PAGE;
    const endIndex = startIndex + PER_PAGE;
    return filteredTerritories.slice(startIndex, endIndex);
  }, [filteredTerritories, page]);

  // ==============================|| API DATA - BATCHED COUNTS ||============================== //

  // One POST /territories/counts/ for just the visible page (~6 ids), not all
  // 100 — replaces the per-card workspace N+1. Keyed on the ids inside the hook.
  const visibleIds = useMemo(
    () => paginatedTerritories.map((t) => t.id),
    [paginatedTerritories]
  );
  const { counts, countsLoading } = useGetTerritoryCounts(visibleIds);

  // ==============================|| HANDLERS ||============================== //

  const handlePageChange = (event, newPage) => {
    setPage(newPage);
  };

  const handleSearchChange = (value) => {
    setGlobalFilter(String(value));
    setPage(1); // Reset to first page on search
  };

  // ==============================|| FILTER HANDLERS ||============================== //

  const handleOpenFilterPanel = () => setFilterPanelOpen(true);
  const handleCloseFilterPanel = () => {
    resetPendingFilters();
    setFilterPanelOpen(false);
  };
  const handleApplyFilters = () => {
    applyFilters();
    setPage(1);
    setFilterPanelOpen(false);
  };
  const handleClearFilters = () => {
    clearFilters();
    setPage(1);
  };
  const handleRemoveFilter = (key) => {
    removeFilter(
      key,
      key === 'owner_scope'
        ? 'all'
        : key === 'owner' || key === 'team'
          ? null
          : ''
    );
    setPage(1);
  };

   // ==============================|| MODAL HANDLERS ||============================== //

  const handleOpenAddModal = () => {
    setAddModalOpen(true);
  };

  const handleCloseAddModal = () => {
    setAddModalOpen(false);
    setInitialFilters({});
  };

  const handleOpenEditModal = (territory) => {
    setSelectedTerritory(territory);
    setEditModalOpen(true);
  };

  const handleCloseEditModal = () => {
    setSelectedTerritory(null);
    setEditModalOpen(false);
  };

  const handleOpenDeleteModal = (territory) => {
    setSelectedTerritory(territory);
    setDeleteModalOpen(true);
  };

  const handleCloseDeleteModal = () => {
    setSelectedTerritory(null);
    setDeleteModalOpen(false);
  };

   // ==============================|| SELECTION HANDLERS ||============================== //

  const handleToggleSelectionMode = () => {
    setSelectionMode(prev => !prev);
    if (selectionMode) {
      // Exiting selection mode - clear selection
      setSelectedRows(new Set());
    }
  };

  const handleSelectRow = (territoryId) => {
    setSelectedRows(prev => {
      const newSet = new Set(prev);
      if (newSet.has(territoryId)) {
        newSet.delete(territoryId);
      } else {
        newSet.add(territoryId);
      }
      return newSet;
    });
  };

  const handleSelectAll = () => {
    // Select all non-system territories on current page
    const selectableIds = paginatedTerritories
      .filter(t => !t.is_system)
      .map(t => t.id);
    
    if (selectedRows.size === selectableIds.length) {
      // All selected -> deselect all
      setSelectedRows(new Set());
    } else {
      // Select all
      setSelectedRows(new Set(selectableIds));
    }
  };

  const handleOpenBulkDeleteModal = () => {
    if (selectedRows.size > 0) {
      setBulkDeleteModalOpen(true);
    }
  };

  const handleCloseBulkDeleteModal = () => {
    setBulkDeleteModalOpen(false);
  };

  const handleBulkDeleteComplete = () => {
    setSelectedRows(new Set());
    setSelectionMode(false);
  };

  // Computed selection values
  const selectableCount = paginatedTerritories.filter(t => !t.is_system).length;
  const allSelected = selectableCount > 0 && selectedRows.size === selectableCount;
  const someSelected = selectedRows.size > 0 && selectedRows.size < selectableCount;


  // ==============================|| RENDER ||============================== //

  return (
    <>
      {/* ==================== HEADER ==================== */}
      <Box sx={{ position: 'relative', marginBottom: 3 }}>
        <Stack direction="row" alignItems="center">
          <Stack
            direction={matchDownSM ? 'column' : 'row'}
            sx={{ width: '100%' }}
            spacing={1}
            justifyContent="space-between"
            alignItems="center"
          >
            {/* Search */}
            <DebouncedInput
              value={globalFilter ?? ''}
              onFilterChange={handleSearchChange}
              placeholder={`Search ${territoriesCount} territories...`}
            />

            {/* Actions — funnel (filter) | Select cluster | New. The funnel
                stays visible and usable in selection mode (filtering while
                selecting is legitimate). The counter lives only in the icon
                tooltips — there is no full-width band. */}
            <Stack direction={matchDownSM ? 'column' : 'row'} alignItems="center" spacing={1}>
              <Badge
                badgeContent={activeFiltersCount}
                color="primary"
                invisible={activeFiltersCount === 0}
              >
                <IconButton color="secondary" onClick={handleOpenFilterPanel}>
                  <FilterOutlined />
                </IconButton>
              </Badge>
              {selectionMode ? (
                <Stack
                  direction="row"
                  alignItems="center"
                  spacing={0.5}
                  sx={{ bgcolor: 'error.lighter', borderRadius: 1, px: 0.5 }}
                >
                  <Tooltip title={`Select all (${selectableCount})`}>
                    <Checkbox
                      checked={allSelected}
                      indeterminate={someSelected}
                      onChange={handleSelectAll}
                      size="small"
                    />
                  </Tooltip>
                  <Tooltip title="Cancel selection">
                    <IconButton color="secondary" onClick={handleToggleSelectionMode}>
                      <CloseOutlined />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title={`Delete ${selectedRows.size} selected`}>
                    <span>
                      <IconButton
                        color="error"
                        onClick={handleOpenBulkDeleteModal}
                        disabled={selectedRows.size === 0}
                      >
                        <DeleteOutlined />
                      </IconButton>
                    </span>
                  </Tooltip>
                </Stack>
              ) : (
                <Tooltip title="Select">
                  <IconButton color="secondary" onClick={handleToggleSelectionMode}>
                    <CheckSquareOutlined />
                  </IconButton>
                </Tooltip>
              )}
              <Button
                variant="contained"
                startIcon={<PlusOutlined />}
                onClick={handleOpenAddModal}
              >
                New Territory
              </Button>
            </Stack>
          </Stack>
        </Stack>
      </Box>

      {/* ==================== ACTIVE FILTER CHIPS ==================== */}
      {activeFiltersCount > 0 && (
        <Stack direction="row" spacing={1} sx={{ mb: 2, flexWrap: 'wrap' }} useFlexGap>
          {filters.owner_scope !== 'all' && (
            <Chip
              size="small"
              label={`Scope: ${filters.owner_scope === 'mine' ? 'Mine' : 'My Team'}`}
              onDelete={() => handleRemoveFilter('owner_scope')}
            />
          )}
          {filters.owner?.id && (
            <Chip
              size="small"
              label={`Owner: ${`${filters.owner.first_name || ''} ${filters.owner.last_name || ''}`.trim() || filters.owner.email || 'Selected'}`}
              onDelete={() => handleRemoveFilter('owner')}
            />
          )}
          {filters.team?.id && (
            <Chip
              size="small"
              label={`Team: ${filters.team.name || 'Selected'}`}
              onDelete={() => handleRemoveFilter('team')}
            />
          )}
          {filters.type && (
            <Chip
              size="small"
              label={`Type: ${filters.type === 'ACCOUNT' ? 'Accounts' : 'Contacts'}`}
              onDelete={() => handleRemoveFilter('type')}
            />
          )}
        </Stack>
      )}


      {/* ==================== TERRITORIES GRID ==================== */}
      <Grid container spacing={3}>
        {paginatedTerritories.length > 0 ? (
          paginatedTerritories.map((territory, index) => (
            <Slide key={territory.id} direction="up" in={true} timeout={50 + index * 50}>
              <Grid item xs={12} sm={6} lg={4}>
                <TerritoryCard
                  territory={territory}
                  count={counts?.[territory.id]?.count}
                  loading={countsLoading}
                  onEdit={handleOpenEditModal}
                  onDelete={handleOpenDeleteModal}
                  selected={selectedRows.has(territory.id)}
                  onSelect={handleSelectRow}
                  selectionMode={selectionMode}
                />
              </Grid>
            </Slide>
          ))
        ) : (
          <Grid item xs={12}>
            <MainCard>
              <Box sx={{ p: 4, textAlign: 'center' }}>
                <Typography variant="h5" color="text.secondary">
                  No territories found
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  {globalFilter 
                    ? `No territories match "${globalFilter}"`
                    : 'Create your first territory to get started'
                  }
                </Typography>
              </Box>
            </MainCard>
          </Grid>
        )}
      </Grid>

      {/* ==================== PAGINATION ==================== */}
      {totalPages > 1 && (
        <Stack spacing={2} sx={{ p: 2.5 }} alignItems="flex-end">
          <Pagination
            sx={{ '& .MuiPaginationItem-root': { my: 0.5 } }}
            count={totalPages}
            size="medium"
            page={page}
            showFirstButton
            showLastButton
            variant="combined"
            color="primary"
            onChange={handlePageChange}
          />
        </Stack>
      )}

      {/* ==================== MODALS ==================== */}

      {/* Add/Edit Territory Modal */}
       <TerritoryModal
          open={addModalOpen || editModalOpen}
          closeModal={() => {
            if (addModalOpen) handleCloseAddModal();
            if (editModalOpen) handleCloseEditModal();
          }}
          territory={selectedTerritory}
          initialFilters={initialFilters}
        />

      {/* Delete Territory Modal */}
      <AlertTerritoryDelete
        territory={selectedTerritory}
        open={deleteModalOpen}
        handleClose={handleCloseDeleteModal}
      />

      {/* Bulk Delete Modal */}
      <AlertTerritoryBulkDelete
        selectedIds={Array.from(selectedRows)}
        open={bulkDeleteModalOpen}
        handleClose={handleCloseBulkDeleteModal}
        onDeleteComplete={handleBulkDeleteComplete}
      />

      {/* Filter Drawer */}
      <TerritoryListFilterPanel
        open={filterPanelOpen}
        onClose={handleCloseFilterPanel}
        pendingFilters={pendingFilters}
        onFilterChange={updatePendingFilter}
        onApply={handleApplyFilters}
        onClear={handleClearFilters}
        hasPendingChanges={hasPendingChanges}
        matchingCount={territoriesCount}
        loading={territoriesLoading}
      />
    </>
  );
}