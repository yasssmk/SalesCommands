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

// project imports
import RoleTable from 'sections/admin/roles/RoleTable';
import PermissionsMatrix from 'sections/admin/roles/PermissionsMatrix';
import useLocalStorage from 'hooks/useLocalStorage';
import RoleModal from 'sections/admin/roles/RoleModal';

// ==============================|| MOCK DATA ||============================== //

/**
 * Mock roles data for development
 * This will be replaced by real API calls in next phase
 */
const MOCK_ROLES = [
  {
    id: 1,
    name: 'Sales Manager',
    is_admin: false,
    is_manager: true,
    is_individual: false,
    users_count: 5,
    created_at: '2024-01-15T10:30:00Z'
  },
  {
    id: 2,
    name: 'Account Executive',
    is_admin: false,
    is_manager: false,
    is_individual: true,
    users_count: 12,
    created_at: '2024-01-20T14:45:00Z'
  },
  {
    id: 3,
    name: 'System Administrator',
    is_admin: true,
    is_manager: false,
    is_individual: false,
    users_count: 2,
    created_at: '2024-01-10T09:00:00Z'
  },
  {
    id: 4,
    name: 'Team Lead',
    is_admin: false,
    is_manager: true,
    is_individual: false,
    users_count: 8,
    created_at: '2024-02-01T11:20:00Z'
  }
];

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
  
  // ==============================|| STATE MANAGEMENT ||============================== //

  // Pagination state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useLocalStorage('roles-page-size', 10);
  
  // Search state
  const [search, setSearch] = useState('');
  
  // Sorting state
  const [sorting, setSorting] = useState([]);

  // Selected tier for matrix preview
  const [previewTier, setPreviewTier] = useState('manager');

  // Modal states
  const [roleModal, setRoleModal] = useState(false);
  const [selectedRole, setSelectedRole] = useState(null);

  // ==============================|| MOCK DATA PROCESSING ||============================== //

  /**
   * Filter and paginate mock data
   * This simulates server-side filtering and pagination
   */
  const processedData = useMemo(() => {
    let filtered = [...MOCK_ROLES];

    // Apply search filter
    if (search) {
      const searchLower = search.toLowerCase();
      filtered = filtered.filter(role => 
        role.name.toLowerCase().includes(searchLower)
      );
    }

    // Apply sorting
    if (sorting.length > 0) {
      const { id: sortKey, desc } = sorting[0];
      filtered.sort((a, b) => {
        let aVal = a[sortKey];
        let bVal = b[sortKey];

        // Handle tier sorting (convert flags to tier string)
        if (sortKey === 'tier') {
          const getTier = (role) => {
            if (role.is_admin) return 'admin';
            if (role.is_manager) return 'manager';
            return 'individual';
          };
          aVal = getTier(a);
          bVal = getTier(b);
        }

        // String comparison
        if (typeof aVal === 'string') {
          return desc 
            ? bVal.localeCompare(aVal)
            : aVal.localeCompare(bVal);
        }

        // Numeric comparison
        return desc ? bVal - aVal : aVal - bVal;
      });
    }

    // Calculate pagination
    const totalCount = filtered.length;
    const startIndex = (page - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    const paginatedData = filtered.slice(startIndex, endIndex);

    return {
      data: paginatedData,
      totalCount
    };
  }, [search, sorting, page, pageSize]);

  const { data: roles, totalCount: rolesCount } = processedData;

  // ==============================|| HANDLERS ||============================== //

  /**
   * Handle pagination changes
   */
  const handlePaginationChange = useCallback(
    ({ page: newPage, pageSize: newPageSize }) => {
      setPage(newPage);
      
      const size = Number(newPageSize);
      if (!isNaN(size) && size > 0 && size !== pageSize) {
        setPageSize(size);
        setPage(1); // Reset to first page on page size change
      }
    },
    [pageSize, setPageSize]
  );

  /**
   * Handle search changes
   */
  const handleSearchChange = useCallback((searchTerm) => {
    setSearch(searchTerm);
    setPage(1); // Reset to first page on search
  }, []);

  /**
   * Handle sorting changes
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
    setSelectedRole(null)
    setRoleModal(true);
  }, []);

  /**
   * Handle viewing role details
   */
  const handleViewRole = useCallback((role) => {
    console.log('👁️ View Role:', role);
    // TODO: setSelectedRole(role) + setViewModal(true) in next phase
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
    console.log('🗑️ Delete Role:', role);
    // TODO: setUserDeleteId(role.id) + setDeleteAlert(true) in next phase
  }, []);

  // ==============================|| BREADCRUMBS ||============================== //

  const breadcrumbLinks = [
    { title: 'Dashboard', to: '/' },
    { title: 'Administration', to: '/admin' },
    { title: 'Roles & Permissions' }
  ];

  // ==============================|| RENDER ||============================== //

  return (
    <>
      {/* Main Content */}
      <Grid container spacing={3}>
        
        {/* Roles Table Section */}
        <Grid item xs={12}>
          <RoleTable
            data={roles}
            loading={false}
            error={null}
            swrKey={null}
            modalToggler={handleAddRole}
            totalCount={rolesCount}
            currentPage={page}
            initialPageSize={pageSize}
            onPaginationChange={handlePaginationChange}
            onSearchChange={handleSearchChange}
            sorting={sorting}
            onSortingChange={handleSortingChange}
            onView={handleViewRole}
            onEdit={handleEditRole}
            onDelete={handleDeleteRole}
          />
        </Grid>

        <RoleModal 
          open={roleModal} 
          modalToggler={setRoleModal} 
          role={selectedRole} 
        />

        {/* Permissions Matrix Preview Section */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box sx={{ mb: 3 }}>
                <Typography variant="h5" gutterBottom>
                  Permissions Matrix Preview
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  This matrix shows the permissions structure for the "{previewTier}" tier.
                  Permissions are defined at the system level and automatically applied to all roles of the same tier.
                </Typography>
              </Box>
              
              <Divider sx={{ mb: 3 }} />
              
              <PermissionsMatrix tier={previewTier} showLegend={true} />
            </CardContent>
          </Card>
        </Grid>

      </Grid>
    </>
  );
}