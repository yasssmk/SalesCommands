// frontend/src/views/admin/roles/list.jsx

'use client';
import { useMemo, useState, useCallback, useEffect } from 'react';

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
import Tooltip from '@mui/material/Tooltip';

// icons
import EyeInvisibleOutlined from '@ant-design/icons/EyeInvisibleOutlined';
import EyeOutlined from '@ant-design/icons/EyeOutlined';
import EditOutlined from '@ant-design/icons/EditOutlined';
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';

// project imports
import ReusableTable from 'components/table/Table';
import PermissionsMatrix from 'sections/admin/roles/PermissionsMatrix';
import RoleModal from 'sections/admin/roles/RoleModal';
import AlertRoleDelete from 'sections/admin/roles/AlertRoleDelete';
import TierBadge from 'sections/admin/roles/TierBadge';
import IconButton from 'components/@extended/IconButton';

// hooks
import useLocalStorage from 'hooks/useLocalStorage';
import { useAuth } from 'hooks/useAuth';

// api
import { useGetRoles } from 'api/admin/roles';
import { tenantKey } from 'api/_swr';

// utils
import { formatDateTime } from 'config/formatters';

// ==============================|| SORT FIELD MAPPING ||============================== //

/**
 * Map frontend column IDs to backend field names for sorting
 * 
 * Used to convert TanStack Table column IDs to Django ORM field names.
 * Example: User sorts by 'tier' column → backend receives 'tier' or '-tier'
 * 
 * @constant
 */
const COLUMN_TO_BACKEND_FIELD = {
  name: 'name',              // Role name
  tier: 'tier',              // Access tier (admin/manager/individual)
  users_count: 'users_count', // Number of users assigned to role
  created_at: 'created_at'   // Creation timestamp
};

// ==============================|| ROLES & PERMISSIONS - LIST ||============================== //

/**
 * Roles & Permissions List Page
 * 
 * Main container page that orchestrates all role management components.
 * Follows the same architectural pattern as User Management for consistency.
 * 
 * Architecture:
 * - Uses ReusableTable component directly (no wrapper)
 * - Columns defined in this file with useMemo
 * - All state management (pagination, search, sorting) handled here
 * - No bulk selection (MVP requirement)
 * 
 * Features:
 * - Role table with server-side pagination, search, and sorting
 * - Permissions matrix preview (collapsible)
 * - Tier-based permissions visualization
 * - Create/Edit/Delete role actions
 * - Admin role protection (cannot edit/delete)
 * 
 * @page
 */
export default function RolesListPage() {

  const { tenantId } = useAuth();

  /**
   * Maximum number of roles per page
   * Prevents excessive API requests and ensures good performance
   */
  const MAX_PAGE_SIZE = 100;
  
  // ==============================|| STATE MANAGEMENT ||============================== //

  // Pagination state with localStorage persistence
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useLocalStorage('roleTablePageSize', 10);
  
   // Validate and cap pageSize to prevent excessive API requests
   const validPageSize = useMemo(() => {
    const parsed = Number(pageSize);
    if (isNaN(parsed) || parsed <= 0) return 10;
    return Math.min(parsed, MAX_PAGE_SIZE);  // Cap at 10 pour role
  }, [pageSize]);
  
  // Search state - triggers server-side filtering
  const [search, setSearch] = useState('');
  
   // Sorting state (TanStack Table format) - triggers server-side ordering
  const [sorting, setSorting] = useState([]);

  // Matrix preview states
  const [previewTier, setPreviewTier] = useState('manager');
  const [showMatrix, setShowMatrix] = useState(true);

 // Modal states for role operations
  const [roleModal, setRoleModal] = useState(false);
  const [selectedRole, setSelectedRole] = useState(null);
  const [deleteModal, setDeleteModal] = useState(false);
  const [roleToDelete, setRoleToDelete] = useState(null);


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
  const _rolesHook = useGetRoles({ 
    page, 
    pageSize: validPageSize, 
    search,
    ordering  
  }) || {};

  const {
    rolesLoading = false,
    roles = [],
    rolesCount = 0,
    rolesError = null
  } = _rolesHook;

  // Build SWR key for cache revalidation
  const swrKey = useMemo(() => {
    const params = new URLSearchParams();
    params.append('page', page);
    params.append('page_size', validPageSize);
    if (search) params.append('search', search);
    if (ordering) params.append('ordering', ordering);
    const url = `/client/roles/${params.toString() ? `?${params.toString()}` : ''}`;
    return tenantKey(url, tenantId);
  }, [page, validPageSize, search, ordering, tenantId]);

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

      if (JSON.stringify(newSorting) !== JSON.stringify(prevSorting)) {
        setPage(1);
      }

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
  
   /**
   * Reset sorting when search changes
   * 
   * Rationale: When user searches for specific roles, the current sort may no longer
   * make sense (e.g., sorting by "Users Count" when only 2 roles match search).
   * Resetting to natural order provides better UX.
   * 
   * Note: This pattern matches User Management for consistency.
   */
  useEffect(() => {
    if (search !== '') {
      setSorting([]);
    }
  }, [search]);

  // ==============================|| COLUMNS DEFINITION ||============================== //

  const columns = useMemo(
    () => [
      // Column 1: Role Name
      {
        header: 'Role Name',
        accessorKey: 'name',
        enableSorting: true,
        cell: ({ getValue }) => (
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Typography variant="subtitle1" fontWeight={500}>
              {getValue() || 'Unnamed Role'}
            </Typography>
          </Stack>
        )
      },

      // Column 2: Tier (with badge)
      {
        header: 'Tier',
        accessorKey: 'tier',
        enableSorting: true,
        cell: ({ getValue}) => {
          const tier = getValue();;
          return <TierBadge tier={tier} />;
        }
      },

      // Column 3: Users Count
      {
        header: 'Users',
        accessorKey: 'users_count',
        enableSorting: true,
        meta: {
          className: 'cell-center'
        },
        cell: ({ getValue }) => (
          <Typography variant="h6" color="text.secondary">
            {getValue() || 0}
          </Typography>
        )
      },

      // Column 4: Created Date
      {
        header: 'Last Update',
        accessorKey: 'updated_at',
        enableSorting: true,
        cell: ({ getValue }) => (
          <Typography variant="body2" color="text.secondary">
            {formatDateTime(getValue())}
          </Typography>
        )
      },

      // Column 5: Actions
      {
        header: 'Actions',
        meta: {
          className: 'cell-center'
        },
        disableSortBy: true,
        enableSorting: false,
        cell: ({ row }) => {
          const role = row.original;
          const isAdminRole = Boolean(role?.is_admin);

          return (
            <Stack direction="row" alignItems="center" justifyContent="center" spacing={0}>
              <Tooltip title={isAdminRole ? 'Admin role cannot be edited' : 'Edit'}>
                <span>
                  <IconButton
                    color="secondary"
                    disabled={isAdminRole}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleEditRole(row.original);
                    }}
                  >
                    <EditOutlined />
                  </IconButton>
                </span>
              </Tooltip>
              <Tooltip title="Delete">
                <IconButton
                  color="secondary"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteRole(row.original);
                  }}
                >
                  <DeleteOutlined />
                </IconButton>
              </Tooltip>
            </Stack>
          );
        }
      }
    ],
    [handleEditRole, handleDeleteRole]
  );

  

  // ==============================|| RENDER ||============================== //

  return (
    <>
      {/* Main Content */}
      <Grid container spacing={3}>
        
        {/* Roles Table Section */}
        <Grid item xs={12}>
          <ReusableTable
            data={roles}
            columns={columns}
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
            addButtonLabel="Add Role"
            addButtonTooltip="Create new role"
            searchPlaceholder={`Search ${rolesCount} roles...`}
            exportFilename="roles-list.csv"
            emptyMessage="No roles found"
            emptyDescription="Start by creating your first role to manage user permissions"
            enableImport={false}
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