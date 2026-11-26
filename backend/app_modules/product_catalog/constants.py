# app_modules/product_catalog/constants.py

PRODUCT_CATALOG_CACHE_TAG = 'product_catalog'


# =============================================================================
# SELLER PROFILE (sprint 2 Game Plan, G6 — PO decision Q6)
# =============================================================================
# The bounds of the tenant's seller profile (SellerProfile), checked by its
# serializer. No field is required.
SELLER_PROFILE_TEXT_MAX_CHARS = 4000          # each free-text field
SELLER_PROFILE_REFERENCES_MAX = 20            # customer references
SELLER_PROFILE_REFERENCE_FIELD_MAX_CHARS = 300  # name / sector / result of one reference
SELLER_PROFILE_REFERENCE_KEYS = ('name', 'sector', 'result')
