# backend/ops/__init__.py

"""
Ops App - Testing & Monitoring Utilities

Provides utility endpoints for:
- Timeout testing (sleep endpoints)
- Error simulation (500, 404)
- Health monitoring (Redis status)

⚠️ Security Note:
These endpoints should be restricted or removed in production.
Consider using middleware to limit access by IP or environment.
"""