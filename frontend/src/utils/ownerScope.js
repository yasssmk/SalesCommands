// frontend/src/utils/ownerScope.js

/**
 * Owner-scope values sent to the backend's `owner_scope` filter.
 *
 * The backend resolves these: 'mine' → owner is self, 'team' → the user's team
 * plus sub-teams (a manager with no team falls back to 'mine'), 'all' → no
 * scope filter. See permissions/owner_scope.py.
 *
 * The constant lives here (a shared util) so both the pure resolver below and
 * the stateful useOwnerScope hook consume it from one place — the natural
 * direction (util owns the constant, hooks depend on the util, never the
 * reverse).
 */
export const OWNER_SCOPES = {
  MINE: 'mine',
  TEAM: 'team',
  ALL: 'all'
};

/**
 * Resolve the DEFAULT owner_scope for a user from their tier — pure, no
 * persistence:
 *
 *   admin       → 'all'
 *   manager     → 'team'
 *   individual  → 'mine'
 *
 * Reads `user.role_tier`, the canonical tier string ('admin'|'manager'|
 * 'individual') from UserRole.get_tier(). The current-user payload
 * (GET /client/user/) is a hand-built dict in UserCurrentView — `role` is the
 * role NAME string and `role_tier` is emitted alongside it (the login and
 * token-refresh payloads carry it too). Any unknown or absent tier falls back
 * to the safe default 'mine' (never 'all').
 *
 * @param {Object|null|undefined} user - the authenticated user (useAuth().user)
 * @returns {'mine'|'team'|'all'}
 */
export function resolveDefaultOwnerScope(user) {
  switch (user?.role_tier) {
    case 'admin':
      return OWNER_SCOPES.ALL;
    case 'manager':
      return OWNER_SCOPES.TEAM;
    case 'individual':
      return OWNER_SCOPES.MINE;
    default:
      // Unknown or absent tier → safe default, never 'all'.
      return OWNER_SCOPES.MINE;
  }
}
