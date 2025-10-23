'use client';
import { useMemo, useState, useCallback, useEffect } from 'react';
import { useSWRConfig } from 'swr';

// material-ui
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid';
import Checkbox from '@mui/material/Checkbox';

// project-import
import IconButton from 'components/@extended/IconButton';

import UserModal from 'sections/admin/users/UserModal';
import UserBulkEditModal from 'sections/admin/users/UserBulkEditModal';
import AlertUserDelete from 'sections/admin/users/AlertUserDelete';
import AlertUserBulkDelete from 'sections/admin/users/AlertUserBulkDelete';
import UserTable from 'sections/admin/users/UserTable';
import ReusableTable from 'components/table/Table';
import SeatsSummary from 'sections/admin/users/SeatsSummary';

import { useGetUsers } from 'api/admin/users';
import { useAuth } from 'hooks/useAuth';
import { tenantKey, revalidateMultiple } from 'api/_swr';
import useLocalStorage from 'hooks/useLocalStorage';

import UserCSVImportModal from 'sections/admin/users/UserCSVImportModal';
import { displayErrorSnackbar, displaySuccessSnackbar, displayWarningSnackbar } from 'utils/displayError';

import { notifyCSVImportOutcome } from 'utils/csvImportNotifications';

// formatting
import { formatDateTime } from 'config/formatters';

// assets
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';
import EditOutlined from '@ant-design/icons/EditOutlined';
import EyeOutlined from '@ant-design/icons/EyeOutlined';
import { useTheme } from '@mui/material/styles';
import CheckCircleFilled from '@ant-design/icons/CheckCircleFilled';

//TEST
import TestErrorButton from 'components/ErrorTest/TestErrorButton';
import TestRateLimitButton from 'components/ErrorTest/TestRateLimitButton'
import TestTimeoutButton from 'components/ErrorTest/TestTimeoutButton';

const COLUMN_TO_BACKEND_FIELD = {
  'full_name': 'last_name',      
  'email': 'email',
  'role_name': 'role__name',      
  'is_superuser': 'is_superuser', 
  'team': 'team__name',           
  'is_active': 'is_active',
  'last_login': 'last_login'
};

// ==============================|| USER LIST ||============================== //

export default function UserListPage() {
  const theme = useTheme();
  const { tenantId } = useAuth();

  const [refreshNonce, setRefreshNonce] = useState(0);

  const { mutate: globalMutate } = useSWRConfig();

  const MAX_PAGE_SIZE = 100;

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useLocalStorage(
    `userTablePageSize`, 10
  );

  const validPageSize = useMemo(() => {
  const parsed = Number(pageSize);
    if (isNaN(parsed) || parsed <= 0) return 10;
    return Math.min(parsed, MAX_PAGE_SIZE);  // ✅ Cap à 100
  }, [pageSize]);

  const [search, setSearch] = useState('');

  const [sorting, setSorting] = useState([]);

  const [csvImportModal, setCsvImportModal] = useState(false);



  const swrKey = useMemo(() => {
    const params = new URLSearchParams();
    params.append('page', page);
    params.append('page_size', validPageSize);  // ✅ Pas pageSize brut
    if (search) params.append('search', search);
    params.append('nonce', String(refreshNonce));
    const url = `/client/users/${params.toString() ? `?${params.toString()}` : ''}`;
    return tenantKey(url, tenantId);
  }, [page, validPageSize, search, tenantId, refreshNonce]);

  const ordering = useMemo(() => {
      if (!sorting || sorting.length === 0) {
        return '';
      }

      // Prendre uniquement le premier tri (TanStack supporte multi-sort mais Django ne le fait pas nativement)
      const firstSort = sorting[0];
      const columnId = firstSort.id;
      const isDesc = firstSort.desc;

      // Récupérer le champ backend correspondant
      const backendField = COLUMN_TO_BACKEND_FIELD[columnId];

      // Si la colonne n'est pas dans le mapping, ignorer le tri
      if (!backendField) {
        return '';
      }

      // Ajouter le préfixe '-' pour le tri descendant
      return isDesc ? `-${backendField}` : backendField;
    }, [sorting]);

    // Hook useGetUsers avec le paramètre ordering
  const _usersHook = useGetUsers({ 
      page, 
      pageSize: validPageSize, 
      search,
      ordering  
    }) || {};

  const {
      usersLoading = false,
      users = [],
      usersCount = 0,
      usersError = null
    } = _usersHook;




  const [open, setOpen] = useState(false);
  const [userModal, setUserModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [userDeleteId, setUserDeleteId] = useState('');
  
  // ✅ State de sélection
  const [selectedRows, setSelectedRows] = useState(new Set());

  const [bulkEditModal, setBulkEditModal] = useState(false);
  const [bulkDeleteAlert, setBulkDeleteAlert] = useState(false);

  

  // ==============================|| HANDLERS ||============================== //

  // ✅ Handler pagination - appelé par UserTable
  const handlePaginationChange = useCallback(
    ({ page: newPage, pageSize: newPageSize }) => {
      // Gestion du changement de page
      setPage(newPage);
      
      // Gestion du changement de pageSize avec persistance
      const size = Number(newPageSize);
      if (!isNaN(size) && size > 0 && size !== validPageSize) {
        setPageSize(size); // Persiste automatiquement dans localStorage
      }
    },
    [setPageSize, validPageSize]
  );

  // ✅ Handler recherche - appelé par UserTable
  const handleSearchChange = useCallback((searchTerm) => {
      setSearch(searchTerm);
      setPage(1);  // Reset à page 1 quand on recherche
    }, []);

  const handleSortingChange = useCallback((updaterOrValue) => {
    setSorting((prevSorting) => {
      // Supporter à la fois les updater functions et les valeurs directes
      const newSorting = typeof updaterOrValue === 'function' 
        ? updaterOrValue(prevSorting) 
        : updaterOrValue;

      // Si le tri change, reset à la page 1
      // (évite d'être sur page 3 avec un nouveau tri qui n'a que 2 pages)
      if (JSON.stringify(newSorting) !== JSON.stringify(prevSorting)) {
        setPage(1);
      }

      return newSorting;
    });
  }, []);

  // Réinitialiser le tri quand la recherche change
  // Évite les incohérences (ex: tri par "Team" alors que la recherche filtre les teams)
  useEffect(() => {
    if (search !== '') {
      setSorting([]);
    }
  }, [search]); 

  const handleClose = useCallback(() => {
      setOpen((prev) => !prev);
    }, []);

  const handleOpenEditModal = useCallback((user) => {
      setSelectedUser(user);
      setUserModal(true);
    }, []);

  const handleOpenDeleteDialog = useCallback(
      (user) => {
        setSelectedUser(user);
        setUserDeleteId(user.id);
        handleClose();
      },
      [handleClose]
    );

  // Handler Import CSV
  const handleImportClick = useCallback(() => {
        setCsvImportModal(true);
    }, []);


  const handleImportCSV = useCallback((response) => {
    // Debug utile en dev
    if (process.env.NODE_ENV === 'development') {
      console.debug('[Users] onImport payload:', response);
    }

    notifyCSVImportOutcome(response, {
      entityLabel: 'user(s)'
    });

    // Force le refetch via revalidateMultiple (comme insertUser)
    revalidateMultiple([
      '/client/users/',           // Liste users (tous les appels)
      '/client/client-accounts/'  // Stats seats
    ]);

    // ✅ Auto-fermeture SEULEMENT si succès clean (100% success, no failures/skips)
    const failed = Number(response?.summary?.failed ?? 0);
    const skipped = Number(response?.summary?.skipped ?? 0);
    const success = Number(response?.summary?.success ?? 0);
    const isCleanSuccess = !!response?.success && failed === 0 && skipped === 0 && success > 0;

    if (isCleanSuccess) {
      setCsvImportModal(false);
    }
    // Sinon: on laisse la modale ouverte pour afficher le BulkImportReport
  }, []); // ✅ Dependencies vides car notifyCSVImportOutcome et revalidateMultiple sont stables

    // +===== Selecion =========+ //

    const handleSelectRow = useCallback((userId) => {
      setSelectedRows(prev => {
        const newSet = new Set(prev);
        if (newSet.has(userId)) {
          newSet.delete(userId);
        } else {
          newSet.add(userId);
        }
        return newSet;
      });
    }, []);

    const handleSelectAll = useCallback((e) => {
      e.stopPropagation();
      if (e.target.checked && users) {
        setSelectedRows(new Set(users.map((user) => user.id)));
      } else {
        setSelectedRows(new Set());
      }
    }, [users]);

  // Calculs
  const allSelected = users && users.length > 0 && selectedRows.size === users.length;
  const someSelected = selectedRows.size > 0 && selectedRows.size < (users?.length || 0);

//   const handleBulkEdit = useCallback(() => {
//   if (selectedRows.size > 0) {
//     setBulkEditModal(true);
//   }
// }, [selectedRows.size]);

// const handleBulkDelete = useCallback(() => {
//   if (selectedRows.size > 0) {
//     setBulkDeleteAlert(true);
//   }
// }, [selectedRows.size]);

// ✅ Ce handler ne fait QUE vider la sélection (appelé par le composant en cas de succès)
const handleBulkDeleteComplete = useCallback(() => {
  setSelectedRows(new Set());
}, []);


  // ==============================|| COLUMNS ||============================== //

  const columns = useMemo(
    () => [
      {
        id: 'select',
        enableSorting: false,
        header: () => {
          return (
            <div onClick={(e) => { e.stopPropagation(); }}>
              <Checkbox
                checked={allSelected}
                indeterminate={someSelected}
                onChange={handleSelectAll}
                onClick={(e) => {
                  e.stopPropagation();
                }}
              />
            </div>
          );
        },
        cell: ({ row }) => {
          const isSelected = selectedRows.has(row.original.id);
          return (
            <div onClick={(e) => { e.stopPropagation(); }}>
              <Checkbox
                checked={isSelected}
                onChange={(e) => {
                  e.stopPropagation();
                  handleSelectRow(row.original.id);
                }}
                onClick={(e) => {
                  e.stopPropagation();
                }}
              />
            </div>
          );
        }
      },
      {
        header: 'User Name',
        accessorKey: 'full_name',
        cell: ({ getValue }) => (
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Typography variant="subtitle1">
              {getValue() || 'No Name'}
            </Typography>
          </Stack>
        )
      },
      {
        header: 'Email',
        accessorKey: 'email',
        cell: ({ getValue }) => (
          <Typography variant="h6">
            {getValue()}
          </Typography>
        )
      },
      {
        header: 'Role',
        accessorKey: 'role_name',
        cell: ({ row }) => {
          const roleTier = row.original.role_tier;
          const roleName = row.original.role_name || 'No Role';
          
          let textColor = 'text.primary';
          if (roleTier === 'admin') {
            textColor = 'error.main';
          } else if (roleTier === 'manager') {
            textColor = 'warning.main';
          } else if (roleTier === 'individual') {
            textColor = 'info.main';
          }
          
          return (
            <Typography 
              variant="h6" 
              sx={{ color: textColor }}
            >
              {roleName}
            </Typography>


          );
        }
      },
      {
        header: 'SuperUser',
        accessorKey: 'is_superuser',
        meta: {
          className: 'cell-center'  
        },
        cell: ({ row }) => (
          row.original.is_superuser ? (
            <CheckCircleFilled 
              style={{ 
                fontSize: '20px',
                color: theme.palette.secondary.main
              }} 
            />
          ) : null
        )
      },
      {
        header: 'Team',
        accessorKey: 'team',
        cell: ({ row }) => {
          const teamName = row.original.team?.name || 'No Team';
          const isNoTeam = !row.original.team;
          
          return (
            <Typography 
              variant="h6"
              color={isNoTeam ? 'text.secondary' : 'inherit'}
            >
              {teamName}
            </Typography>
          );
        }
      },
      {
        header: 'Status',
        accessorKey: 'is_active',
        cell: ({ getValue }) => (
          <Chip color={getValue() ? 'success' : 'error'} label={getValue() ? 'Active' : 'Inactive'} size="small" variant="light" />
        )
      },
      {
        header: 'Last connection',
        accessorKey: 'last_login',
        cell: ({ getValue }) => {
          const v = getValue();
          return <Typography variant="body2" color="text.secondary">{v ? formatDateTime(v) : 'Never'}</Typography>;
        }
      },
      {
        header: 'Actions',
        meta: {
          className: 'cell-center'
        },
        disableSortBy: true,
        enableSorting: false,
        cell: ({ row }) => {
          const collapseIcon =
            row.getCanExpand() && row.getIsExpanded() ? (
              <Tooltip title="Close">
                <EyeOutlined style={{ color: theme.palette.error.main, transform: 'rotate(90deg)' }} />
              </Tooltip>
            ) : (
              <Tooltip title="View">
                <EyeOutlined />
              </Tooltip>
            );

          return (
            <Stack direction="row" alignItems="center" justifyContent="center" spacing={0}>
              <Tooltip title="View">
                <IconButton
                  color="secondary.500"
                  onClick={(e) => {
                    e.stopPropagation();
                    row.toggleExpanded();
                  }}
                >
                  {collapseIcon}
                </IconButton>
              </Tooltip>
              <Tooltip title="Edit">
                <IconButton
                  color="secondary.500"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleOpenEditModal(row.original);
                  }}
                >
                  <EditOutlined />
                </IconButton>
              </Tooltip>
              <Tooltip title="Delete">
                <IconButton
                  color="secondary.500"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleOpenDeleteDialog(row.original);
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
    [theme, handleOpenEditModal, handleOpenDeleteDialog, allSelected, someSelected, handleSelectAll, selectedRows, handleSelectRow]
  );

  return (
    <>

      <Grid container spacing={2} sx={{ mb: 2 }}>
        <SeatsSummary />
      </Grid>

      <ReusableTable
        data={users}
        columns={columns}
        loading={usersLoading}
        error={usersError}
        swrKey={swrKey}
        modalToggler={() => {
          setSelectedUser(null);
          setUserModal(true);
        }}
        totalCount={usersCount} 
        currentPage={page}
        initialPageSize={validPageSize}
        onPaginationChange={handlePaginationChange}
        onSearchChange={handleSearchChange}
        sorting={sorting}                          
        onSortingChange={handleSortingChange}  
        selectedCount={selectedRows.size}
        selectedRows={selectedRows}
        onImport={handleImportClick}
        onEdit={() => {
          if (selectedRows.size === 1) {
            const userId = Array.from(selectedRows)[0];
            const user = users.find(u => u.id === userId);
            if (user) {
              handleOpenEditModal(user);
            }
          } else if (selectedRows.size > 1) {
            setBulkEditModal(true);
          }
        }}
        onDelete={() => {
          if (selectedRows.size === 1) {
            const userId = Array.from(selectedRows)[0];
            const user = users.find(u => u.id === userId);
            if (user) {
              handleOpenDeleteDialog(user);
            }
          } else if (selectedRows.size > 1) {
            setBulkDeleteAlert(true);
          }
        }}

        // Customization (specific to Users)
        addButtonLabel="Add User"
        addButtonTooltip="Add User"
        searchPlaceholder={`Search ${usersCount}  users...`}
        exportFilename="users-list.csv"
        emptyMessage="No users found"
        emptyDescription="Start by adding your first user to the system"
      />

      <UserModal open={userModal} modalToggler={setUserModal} user={selectedUser} />

      <AlertUserDelete
        id={userDeleteId}
        title={selectedUser ? `${selectedUser.first_name} ${selectedUser.last_name}` : ''}
        open={open}
        handleClose={handleClose}
      />
       <UserCSVImportModal          
        open={csvImportModal}
        onClose={() => setCsvImportModal(false)}
        onImport={handleImportCSV}
      />
      {console.log('🔵 Rendering UserBulkEditModal with:', { 
        open: bulkEditModal, 
        selectedUserIds: Array.from(selectedRows),
        selectedCount: selectedRows.size 
      })}


      <UserBulkEditModal
        open={bulkEditModal}
        modalToggler={setBulkEditModal}
        selectedUserIds={Array.from(selectedRows)}
        selectedCount={selectedRows.size}
      />

      <AlertUserBulkDelete
        selectedIds={Array.from(selectedRows)}
        open={bulkDeleteAlert}
        handleClose={() => setBulkDeleteAlert(false)}  // ← Juste fermer
        onDeleteComplete={handleBulkDeleteComplete}     // ← Juste vider
      />

      {/* Test Error Button (dev only) */}
      {/* {process.env.NODE_ENV === 'development' && <TestRateLimitButton/>} */}
      {/* <TestTimeoutButton /> */}
    </>
  );
}