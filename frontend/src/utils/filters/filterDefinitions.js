// frontend/src/utils/filters/filterDefinitions.js
//
// Sprint « Cycle de vie des contacts », 8h — THE inline filter pattern's
// generic part (signals first, accounts / Territory later). A filter
// DEFINITION describes one filter once, for every renderer (the inline
// InlinePillsFilter, the drawer panels):
//   { key,        // the form / state key            e.g. "types"
//     param,      // the server query param           e.g. "signal_type"
//     label,      // its display label                e.g. "Type"
//     multiple,   // several values (repeated param) or one
//     emptyMeans, // no value chosen = EMPTY_MEANS.ALL (send nothing: the
//                 // server's all) | EMPTY_MEANS.SURFACE (send every option
//                 // of this surface)
//     options }   // [{ value, label }] — each one evaluated by the server
//                 // (no dead filter: the server refuses an unknown value,
//                 // a backend contract test checks the options)

export const EMPTY_MEANS = { ALL: "all", SURFACE: "surface" };

/** The definition narrowed to the `values` of a surface (definition order). */
export function restrictFilter(definition, values, overrides = {}) {
  return {
    ...definition,
    options: definition.options.filter((o) => values.includes(o.value)),
    ...overrides,
  };
}

/**
 * The server query params of `values` ({ [key]: string[] }) under
 * `definitions`: { [param]: string[] } — a REPEATED param per value. A value
 * outside the definition's options is never sent; an empty choice follows
 * emptyMeans (ALL → no param, SURFACE → every option).
 */
export function toQueryParams(definitions, values = {}) {
  const params = {};
  definitions.forEach((definition) => {
    const known = definition.options.map((o) => o.value);
    const chosen = (values[definition.key] ?? []).filter((v) => known.includes(v));
    if (chosen.length) params[definition.param] = chosen;
    else if (definition.emptyMeans === EMPTY_MEANS.SURFACE) params[definition.param] = known;
  });
  return params;
}
