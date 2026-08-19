// frontend/src/utils/formatAmount.js
//
// ONE way to render a deal amount, shared by every surface that shows one.
//
// The amount itself is the derived product roll-up (`total_deal_value`) served
// by the API; its unit is the tenant's single currency, served alongside it as
// `currency`. There is no conversion and no per-deal currency — a tenant's rows
// all share its own — so this helper never assumes a code: it takes the one the
// payload carried, and falls back to the bare number when a payload has none.
//
// Extracted from views/businessData/decisionCycles/list.jsx, which introduced
// it for the DC list Amount column and is now one of its three callers (list,
// DC workspace header, DC Products tab). Same output as before the move.

/**
 * Format a deal amount for display: the grouped decimal followed by the
 * tenant's currency code (e.g. "60,000.00 EUR").
 *
 * @param {number|string|null|undefined} value    - the amount
 * @param {string|null|undefined}        currency - ISO-4217 code from the payload
 * @returns {string} the formatted amount, or an em dash when there is no number
 */
export default function formatAmount(value, currency) {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return "—";
  const amount = n.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return currency ? `${amount} ${currency}` : amount;
}
