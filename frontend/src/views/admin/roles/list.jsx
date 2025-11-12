// frontend/src/views/admin/roles/list.jsx

'use client';
import { useMemo, useState, useCallback } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Divider from '@mui/material/Divider';
import Button from '@mui/material/Button';
import Collapse from '@mui/material/Collapse';
import Stack from '@mui/material/Stack';

import EyeInvisibleOutlined from '@ant-design/icons/EyeInvisibleOutlined';
import EyeOutlined from '@ant-design/icons/EyeOutlined';

// project imports
import RoleTable from 'sections/admin/roles/RoleTable';
import PermissionsMatrix from 'sections/admin/roles/PermissionsMatrix';
import useLocalStorage from 'hooks/useLocalStorage';
import RoleModal from 'sections/admin/roles/RoleModal';
import AlertRoleDelete from 'sections/admin/roles/AlertRoleDelete';
import { useGetRoles } from 'api/admin/roles';
import { useAuth } from 'hooks/useAuth';
import { tenantKey } from 'api/_swr';
import TierBadge from 'sections/admin/roles/TierBadge';


// ==============================|| SORT FIELD MAPPING ||============================== //

/**
 * Map frontend column IDs to backend field names
 * Backend uses is_admin for tier sorting
 */
const COLUMN_TO_BACKEND_FIELD = {
  name: 'name',
  tier: 'tier',           
  users_count: 'users_count',
  created_at: 'created_at'
};

// ==============================|| ROLES & PERMISSIONS - LIST ||============================== //

/**
 * Roles & Permissions List Page
 * 
 * Main container page that orchestrates all role management components.
 * 
 * Features:
 * - Breadcrumb navigation
 * - Role table with pagination, search, and sorting
 * - Permissions matrix preview
 * - Action handlers for View/Edit/Delete
 * 
 * @page
 */
export default function RolesListPage() {

  const { tenantId } = useAuth();
  
  // ==============================|| STATE MANAGEMENT ||============================== //

  // Pagination state with localStorage persistence
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useLocalStorage('roles-page-size', 10);
  
  // Validate pageSize
  const validPageSize = useMemo(() => {
    const size = Number(pageSize);
    return !isNaN(size) && size > 0 ? size : 10;
  }, [pageSize]);
  
  // Search state
  const [search, setSearch] = useState('');
  
  // Sorting state (TanStack Table format)
  const [sorting, setSorting] = useState([]);

  // Selected tier for matrix preview
  const [previewTier, setPreviewTier] = useState('manager');

  // Modal states
  const [roleModal, setRoleModal] = useState(false);
  const [selectedRole, setSelectedRole] = useState(null);
  const [deleteModal, setDeleteModal] = useState(false);
  const [roleToDelete, setRoleToDelete] = useState(null);

  // Matrix visibility state
  const [showMatrix, setShowMatrix] = useState(true);

  // ==============================|| COMPUTE ORDERING STRING ||============================== //

  /**
   * Convert TanStack sorting to Django ordering format
   * Example: [{id: 'name', desc: true}] → '-name'
   */
  const ordering = useMemo(() => {
    if (!sorting || !Array.isArray(sorting) || sorting.length === 0) {
      return '';
    }

    return sorting
      .map(({ id, desc }) => {
        const backendField = COLUMN_TO_BACKEND_FIELD[id] || id;
        return desc ? `-${backendField}` : backendField;
      })
      .join(',');
  }, [sorting]);

  // ==============================|| API DATA FETCHING ||============================== //

  /**
   * Fetch roles from API with pagination, search, and sorting
   */
  const {
    roles = [],
    rolesCount = 0,
    rolesLoading = false,
    rolesError = null
  } = useGetRoles(page, validPageSize, search, ordering) || {};

  // Build SWR key for cache revalidation
  const params = new URLSearchParams();
  if (page) params.append('page', page);
  if (validPageSize) params.append('page_size', validPageSize);
  if (search) params.append('search', search);
  if (ordering) params.append('ordering', ordering);
  
  const swrKey = tenantKey(`/client/roles/?${params.toString()}`, tenantId);

  // ==============================|| HANDLERS ||============================== //

  /**
   * Handle pagination changes from table
   */
  const handlePaginationChange = useCallback(
    ({ page: newPage, pageSize: newPageSize }) => {
      setPage(newPage);
      
      const size = Number(newPageSize);
      if (!isNaN(size) && size > 0 && size !== validPageSize) {
        setPageSize(size);
        setPage(1); // Reset to first page on page size change
      }
    },
    [validPageSize, setPageSize]
  );

  /**
   * Handle search changes from table
   */
  const handleSearchChange = useCallback((searchTerm) => {
    setSearch(searchTerm);
    setPage(1); // Reset to first page on search
  }, []);

  /**
   * Handle sorting changes from table
   */
  const handleSortingChange = useCallback((updaterOrValue) => {
    setSorting((prevSorting) => {
      const newSorting = typeof updaterOrValue === 'function' 
        ? updaterOrValue(prevSorting)
        : updaterOrValue;
      return newSorting;
    });
  }, []);

  /**
   * Handle opening "Add Role" modal
   */
  const handleAddRole = useCallback(() => {
    setSelectedRole(null);
    setRoleModal(true);
  }, []);

  /**
   * Handle viewing role details
   */
  const handleViewRole = useCallback((role) => {
    console.log('👁️ View Role:', role);
    // TODO: Implement RoleViewModal in next phase
  }, []);

  /**
   * Handle editing role
   */
  const handleEditRole = useCallback((role) => {
    setSelectedRole(role);
    setRoleModal(true); 
  }, []);

  /**
   * Handle deleting role
   */
  const handleDeleteRole = useCallback((role) => {
      setRoleToDelete(role);
      setDeleteModal(true);
    }, []);

  /**
   * Handle toggling permissions matrix visibility
   */
  const handleToggleMatrix = useCallback(() => {
    setShowMatrix((prev) => !prev);
  }, []);

  /**
   * Handle changing preview tier
   */
  const handleTierChange = useCallback((tier) => {
    setPreviewTier(tier);
  }, []);

  // ==============================|| RENDER ||============================== //

  return (
    <>
      {/* Main Content */}
      <Grid container spacing={3}>
        
        {/* Roles Table Section */}
        <Grid item xs={12}>
          <RoleTable
            data={roles}
            loading={rolesLoading}
            error={rolesError}
            swrKey={swrKey}
            modalToggler={handleAddRole}
            totalCount={rolesCount}
            currentPage={page}
            initialPageSize={validPageSize}
            onPaginationChange={handlePaginationChange}
            onSearchChange={handleSearchChange}
            sorting={sorting}
            onSortingChange={handleSortingChange}
            onView={handleViewRole}
            onEdit={handleEditRole}
            onDelete={handleDeleteRole}
          />
        </Grid>

        {/* Role Add/Edit Modal */}
        <RoleModal 
          open={roleModal} 
          modalToggler={setRoleModal} 
          role={selectedRole} 
        />

        {/* Role Delete Confirmation */}
        <AlertRoleDelete
          role={roleToDelete}
          open={deleteModal}
          handleClose={() => {
            setDeleteModal(false);
            setRoleToDelete(null);
          }}
        />

       {/* Permissions Matrix Preview Section */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              {/* Header with Title and Show/Hide Button */}
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Box>
                  <Typography variant="h5" gutterBottom>
                    Permissions Matrix Preview
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    View the complete permissions structure for each tier level
                  </Typography>
                </Box>
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={showMatrix ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                  onClick={handleToggleMatrix}
                  sx={{ minWidth: 120 }}
                >
                  {showMatrix ? 'Hide' : 'Show'}
                </Button>
              </Box>

              {/* Tier Selection Buttons */}
              <Collapse in={showMatrix}>
                <Box sx={{ mb: 3 }}>
                  <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1.5 }}>
                    Select Tier to Preview:
                  </Typography>
                  <Stack direction="row" spacing={2}>
                    <Box
                      onClick={() => handleTierChange('admin')}
                      sx={{
                        cursor: 'pointer',
                        opacity: previewTier === 'admin' ? 1 : 0.5,
                        transform: previewTier === 'admin' ? 'scale(1.05)' : 'scale(1)',
                        transition: 'all 0.2s ease',
                        '&:hover': {
                          opacity: 1,
                          transform: 'scale(1.05)'
                        }
                      }}
                    >
                      <TierBadge tier="admin" size="medium" />
                    </Box>
                    <Box
                      onClick={() => handleTierChange('manager')}
                      sx={{
                        cursor: 'pointer',
                        opacity: previewTier === 'manager' ? 1 : 0.5,
                        transform: previewTier === 'manager' ? 'scale(1.05)' : 'scale(1)',
                        transition: 'all 0.2s ease',
                        '&:hover': {
                          opacity: 1,
                          transform: 'scale(1.05)'
                        }
                      }}
                    >
                      <TierBadge tier="manager" size="medium" />
                    </Box>
                    <Box
                      onClick={() => handleTierChange('individual')}
                      sx={{
                        cursor: 'pointer',
                        opacity: previewTier === 'individual' ? 1 : 0.5,
                        transform: previewTier === 'individual' ? 'scale(1.05)' : 'scale(1)',
                        transition: 'all 0.2s ease',
                        '&:hover': {
                          opacity: 1,
                          transform: 'scale(1.05)'
                        }
                      }}
                    >
                      <TierBadge tier="individual" size="medium" />
                    </Box>
                  </Stack>
                </Box>

                <Divider sx={{ mb: 3 }} />

                {/* Permissions Matrix */}
                <Box>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    This matrix shows the permissions structure for the <strong>"{previewTier}"</strong> tier.
                    Permissions are defined at the system level and automatically applied to all roles of the same tier.
                  </Typography>
                  <PermissionsMatrix tier={previewTier} showLegend={true} />
                </Box>
              </Collapse>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </>
  );
}