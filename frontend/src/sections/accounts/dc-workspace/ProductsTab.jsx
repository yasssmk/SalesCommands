// frontend/src/sections/accounts/dc-workspace/ProductsTab.jsx

"use client";

import PropTypes from "prop-types";
import { useState, useCallback } from "react";

// MUI
import Autocomplete from "@mui/material/Autocomplete";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// Icons
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  InboxOutlined,
} from "@ant-design/icons";

// Project imports
import {
  useGetDCProducts,
  createDCProduct,
  updateDCProduct,
  deleteDCProduct,
} from "api/accounts/decisionCycles";
import { useGetProductCatalogEntries } from "api/businessData/productCatalog";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";
import formatAmount from "utils/formatAmount";

// Amounts are rendered by the shared helper (utils/formatAmount) with the
// tenant currency the payload carries — the same helper and the same currency
// as the DC list and the workspace header, so one deal reads identically on all
// three. Lines carry their own `currency`; the deal total uses the cycle's.

// ==============================|| ADD / EDIT DIALOG ||============================== //

function ProductFormDialog({
  open,
  onClose,
  onSubmit,
  loading,
  catalogEntries,
  catalogLoading,
  editMode,
  initialValues,
}) {
  const [selectedProduct, setSelectedProduct] = useState(
    initialValues?.product || null,
  );
  const [quantity, setQuantity] = useState(initialValues?.quantity ?? 1);
  const [unitPrice, setUnitPrice] = useState(initialValues?.unitPrice ?? "");
  const [discount, setDiscount] = useState(initialValues?.discount ?? "");
  const [notes, setNotes] = useState(initialValues?.notes ?? "");

  // 0-100, the same bounds the backend enforces
  // (serializers.validate_discount_percent_range + the DB CheckConstraint
  // deal_product_discount_percent_bounds). `inputProps.max` only constrains the
  // spinner — it does not stop a pasted 150 — so the value is checked here too
  // and submission is blocked, turning what would be a 400 into an inline
  // message. The backend check stays the real backstop.
  const discountError =
    discount !== "" && (Number.isNaN(Number(discount)) || Number(discount) < 0 || Number(discount) > 100);

  const handleSubmit = () => {
    const payload = {
      quantity: parseInt(quantity, 10) || 1,
      unit_price: unitPrice !== "" ? unitPrice : null,
      // Empty means "no discount": the column defaults to 0, and sending 0
      // explicitly is what CLEARS a discount on edit (null would be rejected).
      discount_percent: discount !== "" ? discount : 0,
      notes: notes.trim(),
    };
    if (!editMode && selectedProduct) {
      payload.product_catalog_entry = selectedProduct.id;
    }
    onSubmit(payload);
  };

  const canSubmit = (editMode || Boolean(selectedProduct)) && !discountError;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{editMode ? "Edit Product" : "Add Product"}</DialogTitle>
      <DialogContent sx={{ pt: 2, display: "flex", flexDirection: "column", gap: 2 }}>
        {!editMode && (
          <Autocomplete
            options={catalogEntries}
            getOptionLabel={(o) => o.name || ""}
            value={selectedProduct}
            onChange={(_, v) => {
              setSelectedProduct(v);
              if (v?.default_unit_price && !unitPrice) {
                setUnitPrice(v.default_unit_price);
              }
            }}
            loading={catalogLoading}
            renderInput={(params) => (
              <TextField
                {...params}
                label="Product"
                placeholder="Search catalog..."
                size="small"
                required
                sx={{ mt: 1 }}
              />
            )}
            isOptionEqualToValue={(o, v) => o.id === v?.id}
            size="small"
          />
        )}
        <TextField
          label="Quantity"
          type="number"
          size="small"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          inputProps={{ min: 1 }}
        />
        <TextField
          label="Unit Price (override)"
          type="number"
          size="small"
          value={unitPrice}
          onChange={(e) => setUnitPrice(e.target.value)}
          placeholder={
            selectedProduct?.default_unit_price
              ? `Default: ${selectedProduct.default_unit_price}`
              : "Catalog default"
          }
          inputProps={{ min: 0, step: "0.01" }}
        />
        <TextField
          label="Discount %"
          type="number"
          size="small"
          value={discount}
          onChange={(e) => setDiscount(e.target.value)}
          placeholder="0"
          inputProps={{ min: 0, max: 100, step: "0.01" }}
          error={discountError}
          helperText={discountError ? "Discount must be between 0 and 100" : " "}
        />
        <TextField
          label="Notes"
          size="small"
          multiline
          minRows={2}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} size="small">
          Cancel
        </Button>
        <Button
          variant="contained"
          size="small"
          onClick={handleSubmit}
          disabled={!canSubmit || loading}
          startIcon={loading ? <CircularProgress size={14} /> : null}
        >
          {editMode ? "Save" : "Add"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

ProductFormDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onSubmit: PropTypes.func.isRequired,
  loading: PropTypes.bool,
  catalogEntries: PropTypes.array,
  catalogLoading: PropTypes.bool,
  editMode: PropTypes.bool,
  initialValues: PropTypes.object,
};

// ==============================|| DELETE CONFIRM DIALOG ||============================== //

function DeleteConfirmDialog({ open, onClose, onConfirm, productName, loading }) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>Remove Product</DialogTitle>
      <DialogContent>
        <Typography>
          Remove <strong>{productName}</strong> from this deal?
        </Typography>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} size="small">
          Cancel
        </Button>
        <Button
          variant="contained"
          color="error"
          size="small"
          onClick={onConfirm}
          disabled={loading}
          startIcon={loading ? <CircularProgress size={14} /> : null}
        >
          Remove
        </Button>
      </DialogActions>
    </Dialog>
  );
}

DeleteConfirmDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onConfirm: PropTypes.func.isRequired,
  productName: PropTypes.string,
  loading: PropTypes.bool,
};

// ==============================|| PRODUCTS TAB ||============================== //

export default function ProductsTab({ cycleId, cycle }) {
  const { products, productsLoading, productsError, mutateProducts } =
    useGetDCProducts(cycleId);
  const { entries: catalogEntries, entriesLoading: catalogLoading } =
    useGetProductCatalogEntries();

  // Add dialog state
  const [addOpen, setAddOpen] = useState(false);
  const [addLoading, setAddLoading] = useState(false);

  // Edit dialog state
  const [editOpen, setEditOpen] = useState(false);
  const [editLoading, setEditLoading] = useState(false);
  const [editProduct, setEditProduct] = useState(null);

  // Delete dialog state
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteProduct, setDeleteProduct] = useState(null);

  // The deal total comes from the SERVER — `total_deal_value`, the derived
  // roll-up declared once in decision_cycles/services/deal_value_sql.py and now
  // served on the cycle payload. It is NOT re-summed here: a second
  // implementation in JavaScript would drift the moment the formula gains a
  // term. `currency` is its unit, resolved from the tenant server-side.
  //
  // estimated_value is deliberately not displayed any more: no runtime path
  // populates it (TD-75), so the "Estimated value" line it fed was always dead.
  const dealTotal = cycle?.total_deal_value ?? null;
  const dealCurrency = cycle?.currency ?? null;

  // Handlers
  const handleAdd = useCallback(
    async (payload) => {
      setAddLoading(true);
      const result = await createDCProduct(cycleId, payload);
      if (result.success) {
        displaySuccessSnackbar("Product added");
        mutateProducts();
        setAddOpen(false);
      } else {
        displayErrorSnackbar(result);
      }
      setAddLoading(false);
    },
    [cycleId, mutateProducts],
  );

  const handleEdit = useCallback(
    async (payload) => {
      if (!editProduct) return;
      setEditLoading(true);
      const result = await updateDCProduct(cycleId, editProduct.id, payload);
      if (result.success) {
        displaySuccessSnackbar("Product updated");
        mutateProducts();
        setEditOpen(false);
        setEditProduct(null);
      } else {
        displayErrorSnackbar(result);
      }
      setEditLoading(false);
    },
    [cycleId, editProduct, mutateProducts],
  );

  const handleDelete = useCallback(async () => {
    if (!deleteProduct) return;
    setDeleteLoading(true);
    const result = await deleteDCProduct(cycleId, deleteProduct.id);
    if (result.success) {
      displaySuccessSnackbar("Product removed");
      mutateProducts();
      setDeleteOpen(false);
      setDeleteProduct(null);
    } else {
      displayErrorSnackbar(result);
    }
    setDeleteLoading(false);
  }, [cycleId, deleteProduct, mutateProducts]);

  const openEdit = useCallback((product) => {
    setEditProduct(product);
    setEditOpen(true);
  }, []);

  const openDelete = useCallback((product) => {
    setDeleteProduct(product);
    setDeleteOpen(true);
  }, []);

  // Loading
  if (productsLoading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="300px"
      >
        <CircularProgress />
      </Box>
    );
  }

  // Error
  if (productsError) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="300px"
      >
        <Typography color="error">Failed to load products</Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ mb: 2 }}
      >
        <Typography variant="subtitle1" fontWeight={600}>
          Deal Products
        </Typography>
        <Button
          variant="contained"
          size="small"
          startIcon={<PlusOutlined style={{ fontSize: 14 }} />}
          onClick={() => setAddOpen(true)}
        >
          Add Product
        </Button>
      </Stack>

      {/* Empty state */}
      {products.length === 0 ? (
        <Box
          display="flex"
          flexDirection="column"
          justifyContent="center"
          alignItems="center"
          minHeight="200px"
          gap={1}
          sx={{
            border: 1,
            borderColor: "divider",
            borderRadius: 1.5,
            borderStyle: "dashed",
          }}
        >
          <InboxOutlined style={{ fontSize: 36, color: "#8c8c8c" }} />
          <Typography color="text.secondary">
            No products attached to this deal.
          </Typography>
          <Button
            size="small"
            startIcon={<PlusOutlined style={{ fontSize: 12 }} />}
            onClick={() => setAddOpen(true)}
          >
            Add your first product
          </Button>
        </Box>
      ) : (
        <>
          {/* Table */}
          <TableContainer
            sx={{ border: 1, borderColor: "divider", borderRadius: 1.5 }}
          >
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Product</TableCell>
                  <TableCell align="right">Qty</TableCell>
                  <TableCell align="right">Unit Price</TableCell>
                  <TableCell align="right">Discount</TableCell>
                  <TableCell align="right">Line Total</TableCell>
                  <TableCell>Notes</TableCell>
                  <TableCell align="center" sx={{ width: 80 }}>
                    Actions
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {products.map((p) => (
                  <TableRow key={p.id} hover>
                    <TableCell>
                      <Typography variant="body2" fontWeight={500}>
                        {p.product_catalog_entry_detail?.name || "Unknown product"}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">{p.quantity}</TableCell>
                    <TableCell align="right">
                      {formatAmount(
                        p.unit_price || p.product_catalog_entry_detail?.default_unit_price,
                        p.currency,
                      )}
                    </TableCell>
                    {/* Without this column a discounted line's total does not
                        match Qty x Unit Price, with nothing on screen to explain
                        the gap. */}
                    <TableCell align="right">
                      {Number(p.discount_percent) > 0
                        ? `${Number(p.discount_percent)}%`
                        : "\u2014"}
                    </TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600 }}>
                      {formatAmount(p.line_total, p.currency)}
                    </TableCell>
                    <TableCell>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{
                          maxWidth: 200,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                          display: "block",
                        }}
                      >
                        {p.notes || "—"}
                      </Typography>
                    </TableCell>
                    <TableCell align="center">
                      <Stack direction="row" spacing={0.5} justifyContent="center">
                        <Tooltip title="Edit">
                          <IconButton
                            size="small"
                            onClick={() => openEdit(p)}
                          >
                            <EditOutlined style={{ fontSize: 14 }} />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Remove">
                          <IconButton
                            size="small"
                            color="error"
                            onClick={() => openDelete(p)}
                          >
                            <DeleteOutlined style={{ fontSize: 14 }} />
                          </IconButton>
                        </Tooltip>
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          {/* Totals */}
          <Divider sx={{ my: 2 }} />
          <Stack spacing={0.5} alignItems="flex-end" sx={{ pr: 2 }}>
            <Stack direction="row" spacing={2} alignItems="baseline">
              <Typography variant="body2" color="text.secondary">
                Deal total:
              </Typography>
              <Typography variant="subtitle1" fontWeight={700}>
                {formatAmount(dealTotal, dealCurrency)}
              </Typography>
            </Stack>
          </Stack>
        </>
      )}

      {/* Add Dialog */}
      <ProductFormDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onSubmit={handleAdd}
        loading={addLoading}
        catalogEntries={catalogEntries}
        catalogLoading={catalogLoading}
        editMode={false}
      />

      {/* Edit Dialog */}
      {editProduct && (
        <ProductFormDialog
          open={editOpen}
          onClose={() => {
            setEditOpen(false);
            setEditProduct(null);
          }}
          onSubmit={handleEdit}
          loading={editLoading}
          catalogEntries={catalogEntries}
          catalogLoading={catalogLoading}
          editMode
          initialValues={{
            product: editProduct.product_catalog_entry_detail,
            quantity: editProduct.quantity,
            unitPrice: editProduct.unit_price || "",
            discount: editProduct.discount_percent ?? "",
            notes: editProduct.notes || "",
          }}
        />
      )}

      {/* Delete Confirm */}
      <DeleteConfirmDialog
        open={deleteOpen}
        onClose={() => {
          setDeleteOpen(false);
          setDeleteProduct(null);
        }}
        onConfirm={handleDelete}
        productName={deleteProduct?.product_catalog_entry_detail?.name}
        loading={deleteLoading}
      />
    </Box>
  );
}

ProductsTab.propTypes = {
  cycleId: PropTypes.string.isRequired,
  cycle: PropTypes.shape({
    total_deal_value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    currency: PropTypes.string,
  }),
};
