// frontend/src/views/campaigns/list.jsx

"use client";

import { useState, useMemo } from "react";

// material-ui
import useMediaQuery from "@mui/material/useMediaQuery";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import Badge from "@mui/material/Badge";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import Dialog from "@mui/material/Dialog";
import DialogTitle from "@mui/material/DialogTitle";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogActions from "@mui/material/DialogActions";
import Grid from "@mui/material/Grid";
import Pagination from "@mui/material/Pagination";
import Slide from "@mui/material/Slide";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// project imports
import MainCard from "components/MainCard";
import { DebouncedInput } from "components/third-party/react-table";
import CampaignCard from "sections/campaigns/CampaignCard";
import CampaignCreateModal from "sections/campaigns/create/CampaignCreateModal";
import CampaignFilterPanel from "sections/campaigns/CampaignFilterPanel";
import AlertCampaignDelete from "sections/campaigns/AlertCampaignDelete";
import AlertCampaignBulkDelete from "sections/campaigns/AlertCampaignBulkDelete";

// hooks
import useCampaignListFilters from "hooks/useCampaignListFilters";

// api
import { useGetCampaigns, deleteCampaign, CHANNEL_LABELS } from "api/campaigns/campaigns";
import { useGetTerritories } from "api/territories/territories";

// next
import { useRouter } from "next/navigation";

// assets
import PlusOutlined from "@ant-design/icons/PlusOutlined";
import FilterOutlined from "@ant-design/icons/FilterOutlined";
import CheckSquareOutlined from "@ant-design/icons/CheckSquareOutlined";
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import DeleteOutlined from "@ant-design/icons/DeleteOutlined";

// filter chip label maps
const STATUS_LABELS = {
  DRAFT: "Draft",
  ACTIVE: "Active",
  PAUSED: "Paused",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
};

// ==============================|| CAMPAIGNS LIST PAGE ||============================== //

/**
 * Campaigns Page - Sales-facing workspace
 *
 * Displays campaigns as cards for easy navigation.
 * Each card shows type, status, progress, and key metrics.
 */
export default function CampaignsListPage() {
  const matchDownSM = useMediaQuery((theme) => theme.breakpoints.down("sm"));

  // ==============================|| STATE ||============================== //

  const router = useRouter();
  const [globalFilter, setGlobalFilter] = useState("");
  const [page, setPage] = useState(1);
  const [createModalOpen, setCreateModalOpen] = useState(false);

  // Delete confirmation state
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // Selection states
  const [selectedRows, setSelectedRows] = useState(new Set());
  const [selectionMode, setSelectionMode] = useState(false);
  const [bulkDeleteModalOpen, setBulkDeleteModalOpen] = useState(false);

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
    removeFilter,
  } = useCampaignListFilters();

  // Territory list for the territory chip label (SWR-deduped with the drawer).
  const { territories = [] } = useGetTerritories({ page: 1, pageSize: 100 });

  // ==============================|| PAGINATION CONFIG ||============================== //

  const PER_PAGE = 6;

  // ==============================|| API DATA ||============================== //

  const {
    campaigns = [],
    campaignsCount = 0,
    campaignsLoading,
    campaignsError,
    campaignsEmpty,
    mutateCampaigns,
  } = useGetCampaigns({
    page: 1,
    pageSize: 100,
    search: globalFilter,
    filters: apiFilters,
  });

  // ==============================|| PAGINATION ||============================== //

  // TARGETED campaign is always present (created by signal on user creation)
  // Sort it to position 0
  const sortedCampaigns = useMemo(() => {
    return [...campaigns].sort((a, b) => {
      if (a.campaign_type === "TARGETED") return -1;
      if (b.campaign_type === "TARGETED") return 1;
      return 0;
    });
  }, [campaigns]);

  const totalPages = Math.ceil(sortedCampaigns.length / PER_PAGE);

  const paginatedCampaigns = useMemo(() => {
    const startIndex = (page - 1) * PER_PAGE;
    const endIndex = startIndex + PER_PAGE;
    return sortedCampaigns.slice(startIndex, endIndex);
  }, [sortedCampaigns, page]);

  // ==============================|| HANDLERS ||============================== //

  const handlePageChange = (event, newPage) => {
    setPage(newPage);
  };

  const handleSearchChange = (value) => {
    setGlobalFilter(String(value));
    setPage(1);
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
    const OBJECT_KEYS = ["owner", "executor", "team"];
    removeFilter(
      key,
      key === "owner_scope" ? "all" : OBJECT_KEYS.includes(key) ? null : "",
    );
    setPage(1);
  };

  const handleNewCampaign = () => {
    setCreateModalOpen(true);
  };

  const handleOpenCampaign = (campaign) => {
    router.push(`/campaigns/${campaign.id}`);
  };

  const handleDeleteCampaign = (campaign) => {
    setDeleteTarget(campaign);
  };

  const handleDeleteSuccess = () => {
    setDeleteTarget(null);
    mutateCampaigns();
  };

  // ==============================|| SELECTION HANDLERS ||============================== //

  const handleToggleSelectionMode = () => {
    setSelectionMode((prev) => !prev);
    if (selectionMode) {
      // Exiting selection mode - clear selection
      setSelectedRows(new Set());
    }
  };

  const handleSelectRow = (campaignId) => {
    setSelectedRows((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(campaignId)) {
        newSet.delete(campaignId);
      } else {
        newSet.add(campaignId);
      }
      return newSet;
    });
  };

  const handleSelectAll = () => {
    // Select all non-TARGETED campaigns on current page (the TARGETED
    // singleton is protected and cannot be bulk-deleted).
    const selectableIds = paginatedCampaigns
      .filter((c) => c.campaign_type !== "TARGETED")
      .map((c) => c.id);

    if (selectedRows.size === selectableIds.length) {
      setSelectedRows(new Set());
    } else {
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
  const selectableCount = paginatedCampaigns.filter(
    (c) => c.campaign_type !== "TARGETED",
  ).length;
  const allSelected =
    selectableCount > 0 && selectedRows.size === selectableCount;
  const someSelected =
    selectedRows.size > 0 && selectedRows.size < selectableCount;

  // ==============================|| RENDER ||============================== //

  return (
    <>
      {/* ==================== HEADER ==================== */}
      <Box sx={{ position: "relative", marginBottom: 3 }}>
        <Stack direction="row" alignItems="center">
          <Stack
            direction={matchDownSM ? "column" : "row"}
            sx={{ width: "100%" }}
            spacing={1}
            justifyContent="space-between"
            alignItems="center"
          >
            {/* Search */}
            <DebouncedInput
              value={globalFilter ?? ""}
              onFilterChange={handleSearchChange}
              placeholder={`Search ${campaignsCount} campaigns...`}
            />

            {/* Actions — funnel (filter) | Select cluster | New. The funnel
                stays visible and usable in selection mode (filtering while
                selecting is legitimate). The counter lives only in the icon
                tooltips — there is no full-width band. */}
            <Stack
              direction={matchDownSM ? "column" : "row"}
              alignItems="center"
              spacing={1}
            >
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
                  sx={{ bgcolor: "error.lighter", borderRadius: 1, px: 0.5 }}
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
                    <IconButton
                      color="secondary"
                      onClick={handleToggleSelectionMode}
                    >
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
                  <IconButton
                    color="secondary"
                    onClick={handleToggleSelectionMode}
                  >
                    <CheckSquareOutlined />
                  </IconButton>
                </Tooltip>
              )}
              <Button
                variant="contained"
                startIcon={<PlusOutlined />}
                onClick={handleNewCampaign}
              >
                New Campaign
              </Button>
            </Stack>
          </Stack>
        </Stack>
      </Box>

      {/* ==================== ACTIVE FILTER CHIPS ==================== */}
      {activeFiltersCount > 0 && (
        <Stack
          direction="row"
          spacing={1}
          sx={{ mb: 2, flexWrap: "wrap" }}
          useFlexGap
        >
          {filters.owner_scope !== "all" && (
            <Chip
              size="small"
              label={`Scope: ${filters.owner_scope === "mine" ? "Mine" : "My Team"}`}
              onDelete={() => handleRemoveFilter("owner_scope")}
            />
          )}
          {filters.owner?.id && (
            <Chip
              size="small"
              label={`Owner: ${`${filters.owner.first_name || ""} ${filters.owner.last_name || ""}`.trim() || filters.owner.email || "Selected"}`}
              onDelete={() => handleRemoveFilter("owner")}
            />
          )}
          {filters.status && (
            <Chip
              size="small"
              label={`Status: ${STATUS_LABELS[filters.status] || filters.status}`}
              onDelete={() => handleRemoveFilter("status")}
            />
          )}
          {filters.campaign_type && (
            <Chip
              size="small"
              label={`Type: ${filters.campaign_type === "OUTBOUND" ? "Outbound" : "Targeted"}`}
              onDelete={() => handleRemoveFilter("campaign_type")}
            />
          )}
          {filters.territories && (
            <Chip
              size="small"
              label={`Territory: ${territories.find((t) => t.id === filters.territories)?.name || "Selected"}`}
              onDelete={() => handleRemoveFilter("territories")}
            />
          )}
          {filters.executor?.id && (
            <Chip
              size="small"
              label={`Executor: ${`${filters.executor.first_name || ""} ${filters.executor.last_name || ""}`.trim() || filters.executor.email || "Selected"}`}
              onDelete={() => handleRemoveFilter("executor")}
            />
          )}
          {filters.channel_override && (
            <Chip
              size="small"
              label={`Channel: ${CHANNEL_LABELS[filters.channel_override] || filters.channel_override}`}
              onDelete={() => handleRemoveFilter("channel_override")}
            />
          )}
          {filters.team?.id && (
            <Chip
              size="small"
              label={`Team: ${filters.team.name || "Selected"}`}
              onDelete={() => handleRemoveFilter("team")}
            />
          )}
        </Stack>
      )}

      {/* ==================== CAMPAIGNS GRID ==================== */}
      <Grid container spacing={3}>
        {paginatedCampaigns.length > 0 ? (
          paginatedCampaigns.map((campaign, index) => (
            <Slide
              key={campaign.id}
              direction="up"
              in={true}
              timeout={50 + index * 50}
            >
              <Grid item xs={12} sm={6} lg={4}>
                <CampaignCard
                  campaign={campaign}
                  onOpen={handleOpenCampaign}
                  onDelete={handleDeleteCampaign}
                  selected={selectedRows.has(campaign.id)}
                  onSelect={handleSelectRow}
                  selectionMode={selectionMode}
                />
              </Grid>
            </Slide>
          ))
        ) : (
          <Grid item xs={12}>
            <MainCard>
              <Box sx={{ p: 4, textAlign: "center" }}>
                <Typography variant="h5" color="text.secondary">
                  No campaigns found
                </Typography>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mt: 1 }}
                >
                  {globalFilter
                    ? `No campaigns match "${globalFilter}"`
                    : "Create your first campaign to get started"}
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
            sx={{ "& .MuiPaginationItem-root": { my: 0.5 } }}
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

      {/* ==================== CREATE CAMPAIGN MODAL ==================== */}
      <CampaignCreateModal
        open={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        onSuccess={mutateCampaigns}
      />

      {/* ==================== DELETE CAMPAIGN DIALOG (single) ==================== */}
      <AlertCampaignDelete
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        campaign={deleteTarget}
        onSuccess={handleDeleteSuccess}
      />

      {/* ==================== BULK DELETE DIALOG ==================== */}
      <AlertCampaignBulkDelete
        selectedIds={Array.from(selectedRows)}
        open={bulkDeleteModalOpen}
        handleClose={handleCloseBulkDeleteModal}
        onDeleteComplete={handleBulkDeleteComplete}
      />

      {/* Filter Drawer */}
      <CampaignFilterPanel
        open={filterPanelOpen}
        onClose={handleCloseFilterPanel}
        pendingFilters={pendingFilters}
        onFilterChange={updatePendingFilter}
        onApply={handleApplyFilters}
        onClear={handleClearFilters}
        hasPendingChanges={hasPendingChanges}
        matchingCount={campaignsCount}
        loading={campaignsLoading}
      />
    </>
  );
}
