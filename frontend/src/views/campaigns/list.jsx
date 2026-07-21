// frontend/src/views/campaigns/list.jsx

"use client";

import { useState, useMemo } from "react";

// material-ui
import useMediaQuery from "@mui/material/useMediaQuery";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Badge from "@mui/material/Badge";
import IconButton from "@mui/material/IconButton";
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

// hooks
import useCampaignListFilters from "hooks/useCampaignListFilters";

// api
import { useGetCampaigns, deleteCampaign } from "api/campaigns/campaigns";
import { useGetTerritories } from "api/territories/territories";

// next
import { useRouter } from "next/navigation";

// assets
import PlusOutlined from "@ant-design/icons/PlusOutlined";
import FilterOutlined from "@ant-design/icons/FilterOutlined";

// filter chip label maps
const STATUS_LABELS = {
  DRAFT: "Draft",
  ACTIVE: "Active",
  PAUSED: "Paused",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
};
const CHANNEL_LABELS = { AUTO: "Auto", EMAIL_ONLY: "Email only" };

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

  const handleEditCampaign = (campaign) => {
    router.push(`/campaigns/${campaign.id}`);
  };

  const handleDeleteCampaign = (campaign) => {
    setDeleteTarget(campaign);
  };

  const handleDeleteSuccess = () => {
    setDeleteTarget(null);
    mutateCampaigns();
  };

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

            {/* Actions — funnel (filter) | [Select: commit 4] | New */}
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
                  onEdit={handleEditCampaign}
                  onDelete={handleDeleteCampaign}
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

      {/* ==================== DELETE CAMPAIGN DIALOG ==================== */}
      <AlertCampaignDelete
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        campaign={deleteTarget}
        onSuccess={handleDeleteSuccess}
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
