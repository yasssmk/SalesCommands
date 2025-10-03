import PropTypes from 'prop-types';
import React, { Fragment, useMemo, useState, useEffect } from 'react';
import { useSWRConfig } from 'swr';

// material-ui
import { alpha, useTheme } from '@mui/material/styles';
import useMediaQuery from '@mui/material/useMediaQuery';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Stack from '@mui/material/Stack';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import Skeleton from '@mui/material/Skeleton';
import Button from '@mui/material/Button';
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import WarningOutlined from '@ant-design/icons/WarningOutlined';
import ReloadOutlined from '@ant-design/icons/ReloadOutlined';


// third-party
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  getFilteredRowModel,
  getExpandedRowModel,
  useReactTable
} from '@tanstack/react-table';

// project-import
import MainCard from 'components/MainCard';
import ScrollX from 'components/ScrollX';


import { TableHeaderActions, DebouncedInput, HeaderSort, RowSelection, SelectColumnSorting, TablePagination } from 'components/third-party/react-table';
import ExpandingUserDetail from './ExpandingUserDetail';

// utils
import { getErrorDisplayInfo } from 'utils/errorMessages';

// assets
import PlusOutlined from '@ant-design/icons/PlusOutlined';
import IconButton from 'components/@extended/IconButton';

// ==============================|| ERROR DISPLAY COMPONENT ||============================== //

function ErrorDisplay({ error, onRetry, isRetrying }) {
  const errorInfo = getErrorDisplayInfo(error);

  if (!errorInfo) return null;

  return (
    <TableRow>
      <TableCell colSpan={100} sx={{ py: 6, px: 3 }}>
        <Alert
          severity={errorInfo.severity}
          icon={<WarningOutlined style={{ fontSize: 24 }} />}
          action={
            errorInfo.isRetryable && (
              <Button
                color={errorInfo.severity}
                size="small"
                variant="outlined"
                onClick={onRetry}
                disabled={isRetrying}
                startIcon={<ReloadOutlined />}
              >
                {isRetrying ? 'Loading...' : 'Retry'}
              </Button>
            )
          }
        >
          <AlertTitle sx={{ fontWeight: 600 }}>{errorInfo.title}</AlertTitle>
          {errorInfo.message}
        </Alert>
      </TableCell>
    </TableRow>
  );
}

ErrorDisplay.propTypes = {
  error: PropTypes.object,
  onRetry: PropTypes.func.isRequired,
  isRetrying: PropTypes.bool
};

// ==============================|| REACT TABLE ||============================== //

function ReactTable({ 
  data, 
  columns, 
  loading, 
  error, 
  swrKey, 
  modalToggler, 
  selectedCount, 
  selectedRows, 
  onPaginationChange,
  onSearchChange, 
  totalCount,
  initialPageSize = 10 
}) {


  const theme = useTheme();
  const matchDownSM = useMediaQuery(theme.breakpoints.down('sm'));
  const { mutate } = useSWRConfig();

  const [sorting, setSorting] = useState([]);
  const [globalFilter, setGlobalFilter] = useState('');
  const [isRetrying, setIsRetrying] = useState(false);

   const pageIndex = useMemo(() => {
    // Le parent nous dit quelle page afficher via onPaginationChange
    // Ici on assume page 0 par défaut, le parent gère le vrai état
    return 0;
  }, []);

  const pageCount = useMemo(() => {
    const size = Number(initialPageSize) || 10;
    return Math.ceil((totalCount || 0) / size);
  }, [totalCount, initialPageSize]);

  useEffect(() => {
    if (onSearchChange) {
      onSearchChange(globalFilter);
    }
  }, [globalFilter, onSearchChange]);

  const table = useReactTable({
    data,
    columns,
    pageCount,
    state: {
      sorting,
      globalFilter,
      pagination: {
        pageIndex: 0, 
        pageSize: Number(initialPageSize) || 10
      }
    },
    manualPagination: true,
    manualFiltering: true,
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    onPaginationChange: (updater) => {
      // Calculer les nouvelles valeurs
      const currentState = { pageIndex: 0, pageSize: Number(initialPageSize) || 10 };
      const nextState = typeof updater === 'function' ? updater(currentState) : updater;
      
      // Notifier le parent qui gère la vraie pagination
      if (onPaginationChange) {
        onPaginationChange({ 
          page: nextState.pageIndex + 1, 
          pageSize: nextState.pageSize 
        });
      }
    },
    getRowCanExpand: () => true,
    getRowId: (row) => String(row.id),
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
    debugTable: false
  });

  const backColor = alpha(theme.palette.primary.lighter, 0.1);

  const handleRetry = async () => {
    if (!swrKey || isRetrying) return;

    setIsRetrying(true);
    try {
      await mutate(swrKey);
    } catch (err) {
      console.error('Retry failed:', err);
    } finally {
      setTimeout(() => setIsRetrying(false), 500);
    }
  };

 const exportData = useMemo(() => {
    if (!selectedRows || selectedRows.size === 0) {
      return data; // Exporter toutes les données si aucune sélection
    }
    return data.filter(row => selectedRows.has(row.id)); // Exporter seulement les lignes sélectionnées
  }, [data, selectedRows]);

  let headers = [];
  table.getVisibleFlatColumns().map(
    (columns) =>
      columns.columnDef.accessorKey &&
      headers.push({
        label: typeof columns.columnDef.header === 'string' ? columns.columnDef.header : columns.columnDef.header,
        key: columns.columnDef.accessorKey
      })
  );

  return (
    <MainCard content={false}>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={2}
        alignItems="center"
        justifyContent="space-between"
        sx={{ padding: 2, ...(matchDownSM && { '& .MuiOutlinedInput-root, & .MuiFormControl-root': { width: '100%' } }) }}
      >
        <DebouncedInput
          value={globalFilter ?? ''}
          onFilterChange={(value) => setGlobalFilter(String(value))}
          placeholder={loading ? 'Loading...' : `Search ${totalCount} records...`}
          disabled={loading || !!error}
        />

        <Stack direction="row" alignItems="center" spacing={2} sx={{  width: { xs: '100%', sm: 'auto' } }}>
          <SelectColumnSorting {...{ getState: table.getState, getAllColumns: table.getAllColumns, setSorting }} disabled={loading || !!error} />
          <Stack direction="row" spacing={2} alignItems="center" >
          {matchDownSM ? (
            <Tooltip title="Add User">
              <IconButton color="primary" variant="contained" onClick={modalToggler} disabled={loading || !!error}>
                <PlusOutlined />
              </IconButton>
            </Tooltip>
          ) : (
            <Button variant="contained" startIcon={<PlusOutlined />} onClick={modalToggler} disabled={loading || !!error}>
              Add User
            </Button>
          )}

            <TableHeaderActions
              selectedRowCount={selectedCount || 0}
              onEdit={() => {
                // TODO: Implémenter la logique bulk edit
                console.log('Bulk edit clicked');
              }}
              onDelete={() => {
                // TODO: Implémenter la logique bulk delete
                console.log('Bulk delete clicked');
              }}
              onImport={() => {
                // TODO: Implémenter la logique import CSV
                console.log('Import CSV clicked');
              }}
              exportData={exportData}
              exportHeaders={headers}
              exportFilename="users-list.csv"
            />
            </Stack>
        </Stack>
      </Stack>
      <ScrollX>
        <Stack>
          <RowSelection selected={selectedCount || 0} />
          <TableContainer>
            <Table>
              <TableHead>
                {table.getHeaderGroups().map((headerGroup) => (
                  <TableRow key={headerGroup.id}>
                    {headerGroup.headers.map((header) => {
                      if (header.column.columnDef.meta !== undefined && header.column.getCanSort()) {
                        Object.assign(header.column.columnDef.meta, {
                          className: header.column.columnDef.meta.className + ' cursor-pointer prevent-select'
                        });
                      }

                      return (
                        <TableCell
                          key={header.id}
                          {...header.column.columnDef.meta}
                          onClick={header.column.getCanSort() ? header.column.getToggleSortingHandler() : undefined}
                        >
                          {header.isPlaceholder ? null : (
                            <Stack direction="row" spacing={1} alignItems="center">
                              <Box>{flexRender(header.column.columnDef.header, header.getContext())}</Box>
                              {header.column.getCanSort() && <HeaderSort column={header.column} />}
                            </Stack>
                          )}
                        </TableCell>
                      );
                    })}
                  </TableRow>
                ))}
              </TableHead>
              <TableBody>
                {error ? (
                  <ErrorDisplay error={error} onRetry={handleRetry} isRetrying={isRetrying} />
                ) : loading ? (
                  Array.from({ length: 5 }).map((_, index) => (
                    <TableRow key={`skeleton-${index}`}>
                      {columns.map((column, colIndex) => (
                        <TableCell key={`skeleton-cell-${colIndex}`}>
                          <Skeleton animation="wave" height={20} />
                        </TableCell>
                      ))}
                    </TableRow>
                  ))
                ) : data.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={columns.length} align="center" sx={{ py: 6 }}>
                      <Stack spacing={1} alignItems="center">
                        <Typography variant="h6" color="text.secondary">
                          No users found
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {globalFilter 
                            ? `No results for "${globalFilter}"`
                            : 'Start by adding your first user to the system'
                          }
                        </Typography>
                      </Stack>
                    </TableCell>
                  </TableRow>
                ) : (
                  table.getRowModel().rows.map((row) => (
                    <Fragment key={row.id}>
                      <TableRow>
                        {row.getVisibleCells().map((cell) => (
                          <TableCell key={cell.id} {...cell.column.columnDef.meta}>
                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                          </TableCell>
                        ))}
                      </TableRow>
                      {row.getIsExpanded() && (
                        <TableRow sx={{ bgcolor: backColor, '&:hover': { bgcolor: `${backColor} !important` } }}>
                          <TableCell colSpan={row.getVisibleCells().length}>
                            <ExpandingUserDetail data={row.original} />
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
          <>
            <Divider />
            <Box sx={{ p: 2 }}>
              <TablePagination
                {...{
                  setPageSize: table.setPageSize,
                  setPageIndex: table.setPageIndex,
                  getState: table.getState,
                  getPageCount: table.getPageCount,
                  disabled: loading || !!error
                }}
              />
            </Box>
          </>
        </Stack>
      </ScrollX>
    </MainCard>
  );
}

// ==============================|| USER TABLE ||============================== //

const UserTable = React.memo(function UserTable({ 
  data, 
  columns, 
  loading, 
  error, 
  swrKey, 
  modalToggler,
  totalCount = 0,         
  onPaginationChange,      
  onSearchChange,          
  selectedCount,           
  selectedRows,
  initialPageSize = 10               
}) {
  return (
    <ReactTable 
      {...{ 
        data, 
        columns, 
        loading, 
        error, 
        swrKey, 
        modalToggler,
        totalCount,
        onPaginationChange,
        onSearchChange,
        selectedCount,
        selectedRows,
        initialPageSize
      }} 
    />
  );
});

UserTable.propTypes = {
  data: PropTypes.array,
  columns: PropTypes.array,
  loading: PropTypes.bool,
  error: PropTypes.object,
  swrKey: PropTypes.any,
  modalToggler: PropTypes.func,
  selectedCount: PropTypes.number,
  selectedRows: PropTypes.instanceOf(Set),   
  totalCount: PropTypes.number,
  initialPageSize: PropTypes.number,
  onPaginationChange: PropTypes.func,
  onSearchChange: PropTypes.func
};

export default UserTable;