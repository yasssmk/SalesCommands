import PropTypes from 'prop-types';
import React, { Fragment, useMemo, useState } from 'react';
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
import Avatar from 'components/@extended/Avatar';
import IconButton from 'components/@extended/IconButton';
import { DebouncedInput, HeaderSort, IndeterminateCheckbox, RowSelection, SelectColumnSorting, TablePagination, CSVExport } from 'components/third-party/react-table';

import ExpandingUserDetail from './ExpandingUserDetail';

// utils
import { getErrorDisplayInfo } from 'utils/errorMessages';

// assets
import PlusOutlined from '@ant-design/icons/PlusOutlined';

// ==============================|| ERROR DISPLAY COMPONENT ||============================== //

/**
 * Inline error display component with retry action
 * Uses the reusable getErrorDisplayInfo utility for consistent error handling
 */
function ErrorDisplay({ error, onRetry, isRetrying }) {
  const errorInfo = getErrorDisplayInfo(error);

  if (!errorInfo) return null;

  return (
    <TableRow >
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

function ReactTable({ data, columns, loading, error, swrKey, modalToggler }) {
  const theme = useTheme();
  const matchDownSM = useMediaQuery(theme.breakpoints.down('sm'));
  const { mutate } = useSWRConfig();

  const [sorting, setSorting] = useState([]);
  const [rowSelection, setRowSelection] = useState({});
  const [globalFilter, setGlobalFilter] = useState('');
  const [isRetrying, setIsRetrying] = useState(false);

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      rowSelection,
      globalFilter
    },
    enableRowSelection: true,
    onSortingChange: setSorting,
    onRowSelectionChange: setRowSelection,
    onGlobalFilterChange: setGlobalFilter,
    getRowCanExpand: () => true,
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
    debugTable: false
  });

  const backColor = alpha(theme.palette.primary.lighter, 0.1);

  // Handler to retry loading after error
  const handleRetry = async () => {
    if (!swrKey || isRetrying) return;

    setIsRetrying(true);
    try {
      // Revalidate the SWR key (forces a new fetch)
      await mutate(swrKey);
    } catch (err) {
      // Error will be captured by SWR and displayed
      console.error('Retry failed:', err);
    } finally {
      // Small delay to prevent spam clicking
      setTimeout(() => setIsRetrying(false), 500);
    }
  };

  let headers = [];
  table.getVisibleFlatColumns().map(
    (columns) =>
      // @ts-ignore
      columns.columnDef.accessorKey &&
      headers.push({
        label: typeof columns.columnDef.header === 'string' ? columns.columnDef.header : columns.columnDef.header,
        // @ts-ignore
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
          placeholder={loading ? "Loading..." : `Search ${data.length} records...`}
          disabled={loading || !!error}
        />

        <Stack direction="row" alignItems="center" spacing={2} sx={{ width: { xs: '100%', sm: 'auto' } }}>
          <SelectColumnSorting 
            {...{ getState: table.getState, getAllColumns: table.getAllColumns, setSorting }} 
            disabled={loading || !!error}
          />
          <Button 
            variant="contained" 
            startIcon={<PlusOutlined />} 
            onClick={modalToggler} 
            disabled={loading || !!error}
          >
            Add User
          </Button>
        </Stack>
      </Stack>
      <ScrollX>
        <Stack>
          <RowSelection selected={Object.keys(rowSelection).length} />
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
                {/* ✅ PRIORITY 1: ERROR - Displayed first if present */}
                {error ? (
                  <ErrorDisplay 
                    error={error} 
                    onRetry={handleRetry}
                    isRetrying={isRetrying}
                  />
                ) : loading ? (
                  // ✅ PRIORITY 2: LOADING - Skeleton rows
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
                  // ✅ PRIORITY 3: EMPTY STATE - No data message
                  <TableRow>
                    <TableCell colSpan={columns.length} align="center" sx={{ py: 6 }}>
                      <Stack spacing={1} alignItems="center">
                        <Typography variant="h6" color="text.secondary">
                          No users found
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Start by adding your first user to the system
                        </Typography>
                      </Stack>
                    </TableCell>
                  </TableRow>
                ) : (
                  // ✅ PRIORITY 4: DATA STATE - Normal table rows
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

const UserTable = React.memo(function UserTable({ data, columns, loading, error, swrKey, modalToggler }) {
  return <ReactTable {...{ data, columns, loading, error, swrKey, modalToggler }} />;
});

UserTable.propTypes = { 
  data: PropTypes.array, 
  columns: PropTypes.array, 
  loading: PropTypes.bool,
  error: PropTypes.object,        // ✅ Error object from SWR
  swrKey: PropTypes.any,           // ✅ SWR key for mutate()
  modalToggler: PropTypes.func 
};

export default UserTable;