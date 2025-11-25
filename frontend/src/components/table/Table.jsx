// frontend/src/components/table/Table.jsx

import PropTypes from 'prop-types';
import React, { Fragment, useMemo, useState, useEffect, useCallback } from 'react';
import { useSWRConfig } from 'swr';
import { useSearchParams, useRouter } from 'next/navigation';

// material-ui
import { alpha, useTheme } from '@mui/material/styles';
import useMediaQuery from '@mui/material/useMediaQuery';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
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
import Chip from '@mui/material/Chip';
import CloseOutlined from '@ant-design/icons/CloseOutlined';

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
import ExpandingUserDetail from 'sections/admin/users/ExpandingUserDetail';
import MainCard from 'components/MainCard';
import ScrollX from 'components/ScrollX';
import IconButton from 'components/@extended/IconButton';
import ErrorDisplay from './ErrorDisplay';

import { 
  TableHeaderActions, 
  DebouncedInput, 
  HeaderSort, 
  RowSelection, 
  SelectColumnSorting, 
  TablePagination 
} from 'components/third-party/react-table';

// assets
import PlusOutlined from '@ant-design/icons/PlusOutlined';

// ==============================|| REUSABLE TABLE COMPONENT ||============================== //

/**
 * ✅ REUSABLE TABLE COMPONENT
 * 
 * Generic table component with:
 * - Server-side pagination
 * - Sorting
 * - Filtering
 * - Row selection
 * - Expandable rows (optional)
 * - Error handling with intelligent UI
 * - CSV export
 * - Bulk actions
 * 
 * @param {Object} props - Component props
 * @param {Array} props.data - Table data array
 * @param {Array} props.columns - Column definitions (TanStack Table format)
 * @param {boolean} props.loading - Loading state
 * @param {Error} props.error - Error object
 * @param {any} props.swrKey - SWR cache key for revalidation
 * @param {Function} props.modalToggler - Add button click handler
 * @param {number} props.totalCount - Total number of records (for pagination)
 * @param {number} props.currentPage - Current page number (1-indexed)
 * @param {Function} props.onPaginationChange - Pagination change handler
 * @param {Function} props.onSearchChange - Search change handler
 * @param {number} props.selectedCount - Number of selected rows
 * @param {Set} props.selectedRows - Set of selected row IDs
 * @param {number} props.initialPageSize - Initial page size
 * @param {Function} props.onImport - Import handler
 * @param {Function} props.onEdit - Edit handler
 * @param {Function} props.onDelete - Delete handler
 * @param {Array} props.sorting - Sorting state
 * @param {Function} props.onSortingChange - Sorting change handler
 * @param {string} props.addButtonLabel - Label for add button (default: "Add")
 * @param {string} props.addButtonTooltip - Tooltip for add button
 * @param {string} props.searchPlaceholder - Search input placeholder
 * @param {string} props.exportFilename - CSV export filename
 * @param {string} props.emptyMessage - Empty state message
 * @param {string} props.emptyDescription - Empty state description
 * @param {ReactNode} props.expandedRowContent - Function to render expanded row content
 * @param {boolean} props.enableExpanding - Enable row expansion (default: false)
 * @param {boolean} props.enableImport - Enable import CSV button (default: true)
 */
function ReusableTable({ 
  data, 
  columns, 
  loading, 
  error, 
  swrKey, 
  modalToggler, 
  totalCount = 0,
  currentPage = 1,
  onPaginationChange,
  onSearchChange, 
  selectedCount, 
  selectedRows, 
  initialPageSize = 10,
  onImport,
  onEdit,
  onDelete,
  sorting,
  onSortingChange,
  addButtonLabel = 'Add',
  addButtonTooltip = 'Add New',
  searchPlaceholder = 'Search records...',
  exportFilename = 'export.csv',
  emptyMessage = 'No data found',
  emptyDescription = 'Start by adding your first item to the system',
  expandedRowContent = null,
  enableExpanding = false,
  enableImport = true,
  filterConfig = null 
}) {
  const theme = useTheme();
  const matchDownSM = useMediaQuery(theme.breakpoints.down('sm'));
  const { mutate } = useSWRConfig();

  const [globalFilter, setGlobalFilter] = useState('');
  const [isRetrying, setIsRetrying] = useState(false);

  // ✅ Calculate pageIndex from currentPage (1-indexed → 0-indexed)
  const pageIndex = useMemo(() => {
    return Math.max(0, currentPage - 1);
  }, [currentPage]);

  const pageSize = useMemo(() => {
    const n = Number(initialPageSize);
    if (!n || n <= 0) return 10;
    return Math.min(n, 100);
  }, [initialPageSize]);

  const pageCount = useMemo(() => {
    return Math.ceil((totalCount || 0) / pageSize);
  }, [totalCount, pageSize]);

  // ✅ Sync globalFilter with parent
  useEffect(() => {
    if (onSearchChange) {
      onSearchChange(globalFilter);
    }
  }, [globalFilter, onSearchChange]);

  // ✅ Custom handlers for pagination
  const handlePageIndexChange = useCallback((newPageIndex) => {
    if (onPaginationChange) {
      onPaginationChange({
        page: newPageIndex + 1,
        pageSize: Number(initialPageSize) || 10
      });
    }
  }, [onPaginationChange, initialPageSize]);

  const handlePageSizeChange = useCallback((newPageSize) => {
    if (onPaginationChange) {
      onPaginationChange({
        page: 1,
        pageSize: newPageSize
      });
    }
  }, [onPaginationChange]);

  // ✅ TanStack Table instance
  const tableInstance = useReactTable({
    data,
    columns,
    pageCount,
    state: {
      sorting,
      globalFilter,
      pagination: {
        pageIndex: pageIndex,
        pageSize: pageSize
      }
    },
    manualPagination: true,
    manualFiltering: true,
    manualSorting: true,
    onSortingChange: onSortingChange,
    onGlobalFilterChange: setGlobalFilter,
    onPaginationChange: () => {},
    getRowCanExpand: enableExpanding ? () => true : undefined,
    getRowId: (row) => String(row.id),
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getExpandedRowModel: enableExpanding ? getExpandedRowModel() : undefined,
    debugTable: false
  });

  const backColor = alpha(theme.palette.primary.lighter, 0.1);

  // ==============================|| FILTER CHIPS COMPONENT ||============================== //

/**
 * FilterChips - Display active filters as removable chips
 * 
 * Reads URL params and displays them as Material-UI Chips
 * Each chip can be removed to clear that filter from URL
 */
const FilterChips = ({ filterConfig, globalFilter, onSearchChange }) => {
  const searchParams = useSearchParams();
  const router = useRouter();

  // Params to ignore (not display as chips)
  const IGNORED_PARAMS = ['page', 'page_size', 'search', 'ordering', 'nonce'];

  // Get active filters from URL
  const activeFilters = useMemo(() => {
    if (!filterConfig) return [];

    const filters = [];
    const params = Array.from(searchParams.entries());

    params.forEach(([key, value]) => {
      if (IGNORED_PARAMS.includes(key)) return;
      
      const config = filterConfig[key];
      if (!config) return;

      // Resolve display value
      let displayValue = value;
      if (config.resolve) {
        try {
          displayValue = config.resolve(value, data);
        } catch (err) {
          console.warn(`Failed to resolve filter ${key}:`, err);
        }
      }

      filters.push({
        key,
        value,
        label: config.label || key,
        displayValue
      });
    });

    return filters;
  }, [searchParams, filterConfig, data]);

  // Remove specific filter
  const handleRemoveFilter = useCallback((filterKey) => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete(filterKey);
    
    // Reset to page 1 when filter changes
    params.set('page', '1');
    
    router.push(`?${params.toString()}`);
  }, [searchParams, router]);

  // Clear all filters + search
  const handleClearAll = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString());
    
    // Remove all filter params (keep pagination/ordering if needed)
    Array.from(params.keys()).forEach(key => {
      if (!['page_size', 'ordering'].includes(key)) {
        params.delete(key);
      }
    });
    
    // Reset page to 1
    params.set('page', '1');
    
    router.push(`?${params.toString()}`);
    
    // Clear search input
    if (onSearchChange) {
      onSearchChange('');
    }
  }, [searchParams, router, onSearchChange]);

  // Don't render if no active filters
  if (activeFilters.length === 0 && !globalFilter) {
    return null;
  }

  return (
    <Box sx={{ px: 2, pb: 2 }}>
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
        <Typography variant="body2" color="text.secondary">
          Applied filters:
        </Typography>
        
        {activeFilters.map((filter) => (
          <Chip
            key={filter.key}
            label={`${filter.label}: ${filter.displayValue}`}
            onDelete={() => handleRemoveFilter(filter.key)}
            deleteIcon={<CloseOutlined />}
            size="small"
            color="primary"
            variant="outlined"
          />
        ))}

        {globalFilter && (
          <Chip
            label={`Search: "${globalFilter}"`}
            onDelete={() => onSearchChange?.('')}
            deleteIcon={<CloseOutlined />}
            size="small"
            color="default"
            variant="outlined"
          />
        )}

        {(activeFilters.length > 0 || globalFilter) && (
          <Button
            size="small"
            onClick={handleClearAll}
            sx={{ ml: 1 }}
          >
            Clear All
          </Button>
        )}
      </Stack>
    </Box>
  );
};


// ==============================|| Handlers ||============================== //

  // ✅ Retry handler
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

  // ✅ Export data (selected rows or all)
  const exportData = useMemo(() => {
    if (!selectedRows || selectedRows.size === 0) {
      return data;
    }
    return data.filter(row => selectedRows.has(row.id));
  }, [data, selectedRows]);

  // ✅ Export headers
  const headers = useMemo(() => {
    const headerList = [];
    tableInstance.getVisibleFlatColumns().forEach((column) => {
      if (column.columnDef.accessorKey) {
        headerList.push({
          label: column.columnDef.header,
          key: column.columnDef.accessorKey
        });
      }
    });
    return headerList;
  }, [tableInstance]);

  // Export Cached Data

  const cachedData = useMemo(() => (
    tableInstance.getRowModel().rows.map((row) => (
        <Fragment key={row.id}>
        <TableRow>
            {row.getVisibleCells().map((cell) => (
            <TableCell key={cell.id} {...cell.column.columnDef.meta}>
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
            </TableCell>
            ))}
        </TableRow>
        {enableExpanding && row.getIsExpanded() && expandedRowContent && (
            <TableRow sx={{ bgcolor: backColor, '&:hover': { bgcolor: `${backColor} !important` } }}>
            <TableCell colSpan={row.getVisibleCells().length}>
                {expandedRowContent(row.original)}
            </TableCell>
            </TableRow>
        )}
        </Fragment>
    ))
    ), [tableInstance, enableExpanding, expandedRowContent, backColor]);

  return (
    <MainCard content={false}>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={2}
        alignItems="center"
        justifyContent="space-between"
        sx={{ 
          padding: 2, 
          ...(matchDownSM && { 
            '& .MuiOutlinedInput-root, & .MuiFormControl-root': { width: '100%' } 
          }) 
        }}
      >
        <DebouncedInput
          value={globalFilter ?? ''}
          onFilterChange={(value) => setGlobalFilter(String(value))}
          placeholder={loading ? 'Loading...' : searchPlaceholder}
          disabled={!!error}
        />

        <Stack 
          direction="row" 
          alignItems="center" 
          spacing={2} 
          sx={{ width: { xs: '100%', sm: 'auto' } }}
        >
          <SelectColumnSorting 
            {...{ 
              getState: tableInstance.getState, 
              getAllColumns: tableInstance.getAllColumns, 
              setSorting: onSortingChange  
            }} 
            disabled={loading || !!error} 
          />
          <Stack direction="row" spacing={2} alignItems="center">
            {matchDownSM ? (
              <Tooltip title={addButtonTooltip}>
                <IconButton 
                  color="primary" 
                  variant="contained" 
                  onClick={modalToggler} 
                  disabled={loading || !!error}
                >
                  <PlusOutlined />
                </IconButton>
              </Tooltip>
            ) : (
              <Button 
                variant="contained" 
                startIcon={<PlusOutlined />} 
                onClick={modalToggler} 
                disabled={loading || !!error}
              >
                {addButtonLabel}
              </Button>
            )}
            <TableHeaderActions 
              selectedRowCount={selectedCount || 0}    
              onEdit={() => { if (onEdit) onEdit(); }} 
              onDelete={() => { if (onDelete) onDelete(); }} 
              onImport={onImport}
              exportData={exportData}                  
              exportHeaders={headers}                  
              exportFilename={exportFilename}
              enableImport={enableImport}
            />
          </Stack>
        </Stack>
      </Stack>

      <FilterChips 
      filterConfig={filterConfig}
      globalFilter={globalFilter}
      onSearchChange={(value) => setGlobalFilter(String(value))}
      data={data}
    />

      <ScrollX>
        <Stack>
          <RowSelection selected={selectedCount || 0} />
          <>
            <TableContainer>
              <Table>
                <TableHead>
                  {tableInstance.getHeaderGroups().map((headerGroup) => (
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
                            onClick={header.column.getToggleSortingHandler()}
                            {...(header.column.getCanSort() &&
                              header.column.columnDef.meta === undefined && {
                                className: 'cursor-pointer prevent-select'
                              })}
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
                  {loading ? (
                    Array.from({ length: Math.max(1, Math.min(initialPageSize ?? 10, 100)) }).map((_, index) => (
                      <TableRow key={index}>
                        {columns.map((_, colIndex) => (
                          <TableCell key={colIndex}>
                            <Skeleton animation="wave" />
                          </TableCell>
                        ))}
                      </TableRow>
                    ))
                  ) : error ?  (
                    <ErrorDisplay 
                      error={error} 
                      onRetry={handleRetry} 
                      isRetrying={isRetrying}
                      columns={columns}
                      globalFilter={globalFilter}
                      data={data}
                      cachedData={cachedData}  
                      emptyMessage={emptyMessage}
                      emptyDescription={emptyDescription}
                    />
                  ) : data.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={columns.length} align="center" sx={{ py: 6 }}>
                        <Stack spacing={1} alignItems="center">
                          <Typography variant="h6" color="text.secondary">
                            {emptyMessage}
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            {globalFilter 
                              ? `No results for "${globalFilter}"`
                              : emptyDescription
                            }
                          </Typography>
                        </Stack>
                      </TableCell>
                    </TableRow>
                  ) :  (
                    tableInstance.getRowModel().rows.map((row) => (
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
                    setPageSize: handlePageSizeChange,
                    setPageIndex: handlePageIndexChange,
                    getState: tableInstance.getState,
                    getPageCount: tableInstance.getPageCount,
                    initialPageSize,
                    disabled: loading || !!error
                  }}
                />
              </Box>
            </>
          </>
        </Stack>
      </ScrollX>
    </MainCard>
  );
}

ReusableTable.propTypes = {
  data: PropTypes.array,
  columns: PropTypes.array,
  loading: PropTypes.bool,
  error: PropTypes.object,
  swrKey: PropTypes.any,
  modalToggler: PropTypes.func,
  selectedCount: PropTypes.number,
  selectedRows: PropTypes.instanceOf(Set),
  currentPage: PropTypes.number,
  onPaginationChange: PropTypes.func,
  onSearchChange: PropTypes.func,
  totalCount: PropTypes.number,
  initialPageSize: PropTypes.number,
  onImport: PropTypes.func,
  onEdit: PropTypes.func,
  onDelete: PropTypes.func,
  sorting: PropTypes.array,
  onSortingChange: PropTypes.func,
  addButtonLabel: PropTypes.string,
  addButtonTooltip: PropTypes.string,
  searchPlaceholder: PropTypes.string,
  exportFilename: PropTypes.string,
  emptyMessage: PropTypes.string,
  emptyDescription: PropTypes.string,
  expandedRowContent: PropTypes.func,
  enableExpanding: PropTypes.bool,
  enableImport: PropTypes.bool,
  filterConfig: PropTypes.object 
};

export default ReusableTable;