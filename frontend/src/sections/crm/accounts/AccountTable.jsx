import PropTypes from 'prop-types';
import { Fragment, useMemo, useState } from 'react';

// material-ui
import { alpha, useTheme } from '@mui/material/styles';
import useMediaQuery from '@mui/material/useMediaQuery';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Box from '@mui/material/Box';
import Divider from '@mui/material/Divider';

// third-party
import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getFilteredRowModel,
  getExpandedRowModel,
  useReactTable
} from '@tanstack/react-table';
import { rankItem } from '@tanstack/match-sorter-utils';

// project-import
import ScrollX from 'components/ScrollX';
import MainCard from 'components/MainCard';
import {
  CSVExport,
  DebouncedInput,
  TablePagination,
  SelectColumnVisibility
} from 'components/third-party/react-table';

// assets
import PlusOutlined from '@ant-design/icons/PlusOutlined';

export const fuzzyFilter = (row, columnId, value, addMeta) => {
  const itemRank = rankItem(row.getValue(columnId), value);
  addMeta(itemRank);
  return itemRank.passed;
};

const getVisibleColumns = (columns) => {
  return columns.filter(column => 
    column.columnDef.accessorKey && 
    !['select', 'actions'].includes(column.columnDef.accessorKey)
  );
};

export default function AccountTable({ data, columns, modalToggler, hasSelectedAccount }) {
  const theme = useTheme();
  const downSM = useMediaQuery(theme.breakpoints.down('sm'));
  
  const [columnVisibility, setColumnVisibility] = useState({});
  const [globalFilter, setGlobalFilter] = useState('');
  
  const table = useReactTable({
    data,
    columns,
    state: {
      columnVisibility,
      globalFilter
    },
    onColumnVisibilityChange: setColumnVisibility,
    onGlobalFilterChange: setGlobalFilter,
    getRowCanExpand: () => true,
    getFilteredRowModel: getFilteredRowModel(),
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
    globalFilterFn: fuzzyFilter,
    debugTable: true
  });

  const backColor = alpha(theme.palette.primary.lighter, 0.1);
  
  // Get headers for CSV export
  const csvHeaders = useMemo(() => {
    const visibleColumns = getVisibleColumns(table.getVisibleLeafColumns());
    return visibleColumns.map(column => ({
      label: typeof column.columnDef.header === 'string' ? column.columnDef.header : column.id,
      key: column.columnDef.accessorKey
    }));
  }, [table.getVisibleLeafColumns()]);

  // Prepare data for CSV export
  const csvData = useMemo(() => {
    return table.getRowModel().rows.map(row => {
      const rowData = {};
      csvHeaders.forEach(header => {
        rowData[header.key] = row.original[header.key];
      });
      return rowData;
    });
  }, [table.getRowModel().rows, csvHeaders]);

  return (
    <MainCard content={false}>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={2}
        alignItems="center"
        justifyContent="space-between"
        sx={{ padding: 2, ...(downSM && { '& .MuiOutlinedInput-root, & .MuiFormControl-root': { width: '100%' } }) }}
      >
        <DebouncedInput
          value={globalFilter ?? ''}
          onFilterChange={(value) => setGlobalFilter(String(value))}
          placeholder={`Search ${data.length} records...`}
        />

        <Stack direction="row" spacing={2} alignItems="center">
          <SelectColumnVisibility
            {...{
              getVisibleLeafColumns: table.getVisibleLeafColumns,
              getIsAllColumnsVisible: table.getIsAllColumnsVisible,
              getToggleAllColumnsVisibilityHandler: table.getToggleAllColumnsVisibilityHandler,
              getAllColumns: table.getAllColumns
            }}
          />
          <Button variant="contained" startIcon={<PlusOutlined />} onClick={modalToggler}>
            {hasSelectedAccount ? 'Modify Accounts' : 'Add Account'}
          </Button>
          {csvHeaders.length > 0 && (
            <CSVExport
              data={csvData}
              headers={csvHeaders}
              filename="accounts-list.csv"
            />
          )}
        </Stack>
      </Stack>
      
      <ScrollX>
        <TableContainer>
          <Table>
            <TableHead>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <TableCell key={header.id} {...header.column.columnDef.meta}>
                      {header.isPlaceholder ? null : (
                        <Box>
                          {flexRender(header.column.columnDef.header, header.getContext())}
                        </Box>
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableHead>
            <TableBody>
              {table.getRowModel().rows.map((row) => (
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
              ))}
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
                getPageCount: table.getPageCount
              }}
            />
          </Box>
        </>
      </ScrollX>
    </MainCard>
  );
}

AccountTable.propTypes = {
  data: PropTypes.array,
  columns: PropTypes.array,
  modalToggler: PropTypes.func
};