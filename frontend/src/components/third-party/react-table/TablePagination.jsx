'use client';
import PropTypes from 'prop-types';
import { useState, useEffect } from 'react';

// material-ui
import FormControl from '@mui/material/FormControl';
import Grid from '@mui/material/Unstable_Grid2';
import MenuItem from '@mui/material/MenuItem';
import Pagination from '@mui/material/Pagination';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

// ==============================|| TABLE PAGINATION ||============================== //

export default function TablePagination({ 
  getPageCount, 
  setPageIndex, 
  setPageSize, 
  getState, 
  initialPageSize 
}) {
  const [open, setOpen] = useState(false);
  const MAX_PAGE_SIZE = 100;
  
  // ✅ État local pour le TextField "Go to"
  const currentPageIndex = getState().pagination.pageIndex;
  const [pageInputValue, setPageInputValue] = useState(String(currentPageIndex + 1));

  // ✅ Sync avec la page réelle quand elle change (via pagination cliquable)
  useEffect(() => {
    setPageInputValue(String(currentPageIndex + 1));
  }, [currentPageIndex]);
  
  let options = [10, 25, 50, 100];

  if (initialPageSize) {
    options = [...options, initialPageSize]
      .filter((item, index) => [...options, initialPageSize].indexOf(item) === index)
      .sort(function (a, b) {
        return a - b;
      });
  }

  const handleClose = () => {
    setOpen(false);
  };

  const handleOpen = () => {
    setOpen(true);
  };

  const handleChangePagination = (event, value) => {
    setPageIndex(value - 1);
  };

  const handleChange = (event) => {
    // ✅ Capper la valeur pour éviter les crashes
    const v = Math.max(1, Math.min(Number(event.target.value) || 10, MAX_PAGE_SIZE));
    setPageSize(v);
  };

  // ✅ Handler pour la saisie libre
  const handlePageInputChange = (e) => {
    setPageInputValue(e.target.value);
  };

  // ✅ Validation et application de la page
  const applyPageInput = () => {
    const maxPage = getPageCount();
    
    if (pageInputValue === '' || pageInputValue === null) {
      // Si vide, revenir à la page actuelle
      setPageInputValue(String(currentPageIndex + 1));
      return;
    }
    
    let page = Number(pageInputValue);
    
    // Valider et capper
    if (isNaN(page) || page < 1) {
      page = 1;
    } else if (page > maxPage) {
      page = maxPage;
    }
    
    // Mettre à jour l'affichage avec la valeur corrigée
    setPageInputValue(String(page));
    
    // Appliquer la page validée (0-indexed)
    setPageIndex(page - 1);
  };

  return (
    <Grid spacing={1} container alignItems="center" justifyContent="space-between" sx={{ width: 'auto' }}>
      <Grid>
        <Stack direction="row" spacing={1} alignItems="center">
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="caption" color="secondary">
              Row per page
            </Typography>
            <FormControl sx={{ m: 1 }}>
              <Select
                id="demo-controlled-open-select"
                open={open}
                onClose={handleClose}
                onOpen={handleOpen}
                value={getState().pagination.pageSize}
                onChange={handleChange}
                size="small"
                sx={{ '& .MuiSelect-select': { py: 0.75, px: 1.25 } }}
              >
                {options.map((option) => (
                  <MenuItem key={option} value={option}>
                    {option}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Stack>
          <Typography variant="caption" color="secondary">
            Go to
          </Typography>
          <TextField
            size="small"
            type="number"
            value={pageInputValue}
            onChange={handlePageInputChange}
            onBlur={applyPageInput}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                applyPageInput();
              }
            }}
            inputProps={{
              min: 1,
              max: getPageCount(),
              step: 1
            }}
            sx={{ '& .MuiOutlinedInput-input': { py: 0.75, px: 1.25, width: 36 } }}
          />
        </Stack>
      </Grid>
      <Grid sx={{ mt: { xs: 2, sm: 0 } }}>
        <Pagination
          sx={{ '& .MuiPaginationItem-root': { my: 0.5 } }}
          count={getPageCount()}
          page={getState().pagination.pageIndex + 1}
          onChange={handleChangePagination}
          color="primary"
          variant="combined"
          showFirstButton
          showLastButton
        />
      </Grid>
    </Grid>
  );
}

TablePagination.propTypes = {
  getPageCount: PropTypes.func,
  setPageIndex: PropTypes.func,
  setPageSize: PropTypes.func,
  getState: PropTypes.func,
  initialPageSize: PropTypes.number
};