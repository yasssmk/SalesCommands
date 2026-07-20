// frontend/src/sections/businessData/products/AlertProductCatalogDelete.jsx

import PropTypes from "prop-types";
import { useState } from "react";

// material-ui
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogContent from "@mui/material/DialogContent";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// project imports
import Avatar from "components/@extended/Avatar";
import { PopupTransition } from "components/@extended/Transitions";
import { deleteProductCatalogEntry } from "api/businessData/productCatalog";
import {
  displayErrorSnackbar,
  displaySuccessSnackbar,
} from "utils/displayError";

// assets
import DeleteFilled from "@ant-design/icons/DeleteFilled";

// ==============================|| PRODUCT CATALOG - DELETE ALERT ||============================== //

/**
 * Confirmation dialog for single product catalog entry deletion.
 *
 * Hard delete — no soft-delete flag on the model. The admin must confirm
 * explicitly. Downstream FK relations (DealProduct ↔ ProductCatalog)
 * govern their own cascade behaviour through their on_delete settings.
 *
 * @param {Object}   entry       - Entry to delete (with id, name)
 * @param {boolean}  open        - Dialog open state
 * @param {Function} handleClose - Function to close the dialog
 */
export default function AlertProductCatalogDelete({ entry, open, handleClose }) {
  const [deleting, setDeleting] = useState(false);

  const deleteHandler = async () => {
    if (!entry?.id) return;

    try {
      setDeleting(true);
      const result = await deleteProductCatalogEntry(entry.id);

      if (result?.success) {
        displaySuccessSnackbar("Product deleted successfully");
        handleClose?.();
      } else {
        displayErrorSnackbar(result);
        // Dialog stays open on error so the user sees the message
        // and can retry or cancel explicitly.
      }
    } catch (err) {
      displayErrorSnackbar(err);
    } finally {
      setDeleting(false);
    }
  };

  const displayName = entry?.name || "";

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      keepMounted
      TransitionComponent={PopupTransition}
      maxWidth="xs"
      aria-labelledby="product-catalog-delete-title"
      aria-describedby="product-catalog-delete-description"
    >
      <DialogContent sx={{ mt: 2, my: 1 }}>
        <Stack alignItems="center" spacing={3.5}>
          <Avatar
            color="error"
            sx={{ width: 72, height: 72, fontSize: "1.75rem" }}
          >
            <DeleteFilled />
          </Avatar>

          <Stack spacing={2}>
            <Typography variant="h4" align="center">
              Are you sure you want to delete?
            </Typography>
            <Typography align="center">
              By deleting{" "}
              <Typography variant="subtitle1" component="span">
                &quot;{displayName}&quot;{" "}
              </Typography>
              from the product catalog, this entry will be permanently removed.
            </Typography>
          </Stack>

          <Stack direction="row" spacing={2} sx={{ width: 1 }}>
            <Button
              fullWidth
              onClick={handleClose}
              color="secondary"
              variant="outlined"
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button
              fullWidth
              color="error"
              variant="contained"
              onClick={deleteHandler}
              autoFocus
              disabled={deleting}
            >
              {deleting ? "Deleting..." : "Delete"}
            </Button>
          </Stack>
        </Stack>
      </DialogContent>
    </Dialog>
  );
}

AlertProductCatalogDelete.propTypes = {
  entry: PropTypes.shape({
    id: PropTypes.string,
    name: PropTypes.string,
  }),
  open: PropTypes.bool,
  handleClose: PropTypes.func,
};
