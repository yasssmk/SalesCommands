"""
Permission System Configuration

This module handles feature flags and configuration for the permission system.
Allows gradual rollout with module-by-module activation.

Configuration is read from Django settings:
    PERMISSIONS_CONFIG = {
        'GLOBAL_ENABLED': False,  # Master kill switch
        'MODULES': {
            'accounts': False,
            'contacts': False,
            # ... etc
        }
    }
"""

from typing import Dict, Any, Optional, List
from django.conf import settings
from django.core.signals import setting_changed
from django.dispatch import receiver
from core.logging import get_logger

logger = get_logger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    'GLOBAL_ENABLED': True,  # Master kill switch - set to False for safety
    'DEBUG': False,  # Enable debug logging
    'AUDIT_ENABLED': False,  # Enable audit logging
    'CACHE_TIMEOUT': 300,  # Cache timeout in seconds (5 minutes)
    'MODULES': {
        'accounts': True,
        'contacts': False,
        'activities': False,
        'leads': False,
        'opportunities': False,
        'campaign': False,
        'pipelines': False,
        'templates': False,
        'users': True,
        'roles': True,
        'teams': True,
        'products': False,
    },
    'AUDIT_LOGGER': 'permissions.audit',  # Logger name for audit logs
    'ENABLE_OBJECT_PERMISSIONS': False,  # Enable object-level permission checks
    'STRICT_MODE': False,  # If True, fail closed on any error
}

# Cache for configuration
_config_cache: Optional[Dict[str, Any]] = None


def get_config() -> Dict[str, Any]:
    """
    Get the permission configuration from Django settings.
    
    Returns:
        Configuration dictionary
    """
    global _config_cache
    
    if _config_cache is not None:
        return _config_cache
    
    # Get from settings or use defaults
    config = getattr(settings, 'PERMISSIONS_CONFIG', {})
    
    # Merge with defaults
    merged_config = DEFAULT_CONFIG.copy()
    
    # Update top-level settings
    for key in ['GLOBAL_ENABLED', 'DEBUG', 'AUDIT_ENABLED', 'CACHE_TIMEOUT', 
                'AUDIT_LOGGER', 'ENABLE_OBJECT_PERMISSIONS', 'STRICT_MODE']:
        if key in config:
            merged_config[key] = config[key]
    
    # Update module settings
    if 'MODULES' in config:
        merged_config['MODULES'].update(config['MODULES'])
    
    _config_cache = merged_config
    return merged_config


def is_enabled() -> bool:
    """
    Check if the permission system is globally enabled.
    
    This is the master kill switch. If False, all permission
    checks are bypassed.
    
    Returns:
        True if system is enabled
    """
    config = get_config()
    return bool(config.get('GLOBAL_ENABLED', False))


def is_module_enabled(module: str) -> bool:
    """
    Check if permissions are enabled for a specific module.
    
    Args:
        module: Module name (e.g., 'accounts')
        
    Returns:
        True if module is enabled
    """
    # If global is disabled, everything is disabled
    if not is_enabled():
        return False
    
    config = get_config()
    modules = config.get('MODULES', {})
    
    # Check specific module setting
    return bool(modules.get(module, False))


def is_debug_enabled() -> bool:
    """
    Check if debug mode is enabled.
    
    Returns:
        True if debug mode is on
    """
    config = get_config()
    return bool(config.get('DEBUG', False))


def is_audit_enabled() -> bool:
    """
    Check if audit logging is enabled.
    
    Returns:
        True if audit logging is on
    """
    config = get_config()
    return bool(config.get('AUDIT_ENABLED', False))


def is_strict_mode() -> bool:
    """
    Check if strict mode is enabled.
    
    In strict mode, any error results in permission denied
    (fail closed instead of fail open).
    
    Returns:
        True if strict mode is on
    """
    config = get_config()
    return bool(config.get('STRICT_MODE', False))


def get_cache_timeout() -> int:
    """
    Get cache timeout in seconds.
    
    Returns:
        Cache timeout in seconds
    """
    config = get_config()
    return int(config.get('CACHE_TIMEOUT', 300))


def get_audit_logger_name() -> str:
    """
    Get the logger name for audit logs.
    
    Returns:
        Logger name
    """
    config = get_config()
    return config.get('AUDIT_LOGGER', 'permissions.audit')


def get_enabled_modules() -> List[str]:
    """
    Get list of enabled modules.
    
    Returns:
        List of module names that are enabled
    """
    if not is_enabled():
        return []
    
    config = get_config()
    modules = config.get('MODULES', {})
    
    return [
        module_name 
        for module_name, enabled in modules.items() 
        if enabled
    ]


def enable_module(module: str) -> None:
    """
    Enable permissions for a module.
    
    This modifies the in-memory configuration only.
    To persist, update Django settings.
    
    Args:
        module: Module name to enable
    """
    config = get_config()
    if 'MODULES' not in config:
        config['MODULES'] = {}
    config['MODULES'][module] = True
    
    # Clear cache to force reload
    global _config_cache
    _config_cache = None


def disable_module(module: str) -> None:
    """
    Disable permissions for a module.
    
    This modifies the in-memory configuration only.
    To persist, update Django settings.
    
    Args:
        module: Module name to disable
    """
    config = get_config()
    if 'MODULES' not in config:
        config['MODULES'] = {}
    config['MODULES'][module] = False
    
    # Clear cache to force reload
    global _config_cache
    _config_cache = None


def enable_global() -> None:
    """
    Enable the permission system globally.
    
    This modifies the in-memory configuration only.
    To persist, update Django settings.
    """
    config = get_config()
    config['GLOBAL_ENABLED'] = True
    
    # Clear cache to force reload
    global _config_cache
    _config_cache = None


def disable_global() -> None:
    """
    Disable the permission system globally.
    
    This modifies the in-memory configuration only.
    To persist, update Django settings.
    """
    config = get_config()
    config['GLOBAL_ENABLED'] = False
    
    # Clear cache to force reload
    global _config_cache
    _config_cache = None


def reset_config_cache() -> None:
    """
    Reset the configuration cache.
    
    Forces reload from Django settings on next access.
    """
    global _config_cache
    _config_cache = None


# Listen for settings changes to clear cache
@receiver(setting_changed)
def reload_config_on_setting_changed(sender, setting, **kwargs):
    """
    Clear config cache when settings change.
    
    Args:
        sender: Signal sender
        setting: Setting name that changed
    """
    if setting == 'PERMISSIONS_CONFIG':
        reset_config_cache()


class PermissionConfig:
    """
    Context manager for temporary configuration changes.
    
    Useful for testing or temporary overrides.
    
    Example:
        with PermissionConfig(GLOBAL_ENABLED=True, MODULES={'accounts': True}):
            # Permissions are enabled here
            pass
        # Original configuration restored
    """
    
    def __init__(self, **overrides):
        """
        Initialize with configuration overrides.
        
        Args:
            **overrides: Configuration keys to override
        """
        self.overrides = overrides
        self.original_config = None
        self.original_cache = None
    
    def __enter__(self):
        """Enter context - apply overrides."""
        global _config_cache
        
        # Save original
        self.original_cache = _config_cache
        self.original_config = get_config().copy() if _config_cache else None
        
        # Apply overrides
        if _config_cache is None:
            _config_cache = get_config()
        
        for key, value in self.overrides.items():
            if key == 'MODULES' and isinstance(value, dict):
                _config_cache['MODULES'].update(value)
            else:
                _config_cache[key] = value
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context - restore original configuration."""
        global _config_cache
        _config_cache = self.original_cache


def validate_configuration() -> Dict[str, List[str]]:
    """
    Validate the current configuration.
    
    Returns:
        Dictionary with 'errors' and 'warnings' lists
    """
    errors = []
    warnings = []
    config = get_config()
    
    # Check if globally enabled but no modules enabled
    if config.get('GLOBAL_ENABLED') and not get_enabled_modules():
        warnings.append("Global permissions enabled but no modules are enabled")
    
    # Check for unknown modules
    known_modules = set(DEFAULT_CONFIG['MODULES'].keys())
    configured_modules = set(config.get('MODULES', {}).keys())
    unknown = configured_modules - known_modules
    if unknown:
        warnings.append(f"Unknown modules in configuration: {unknown}")
    
    # Check debug in production
    if config.get('DEBUG') and not settings.DEBUG:
        warnings.append("Permission debug mode enabled in production")
    
    # Check strict mode
    if not config.get('STRICT_MODE'):
        warnings.append("Strict mode disabled - system will fail open on errors")
    
    return {
        'errors': errors,
        'warnings': warnings
    }


# Audit logging helper
def audit_log(action: str, module: str, user, scope: str, allowed: bool, **extra):
    """
    Log permission check for audit.
    
    Args:
        action: Action attempted
        module: Module accessed
        user: User making request
        scope: Scope determined
        allowed: Whether access was allowed
        **extra: Additional context
    """
    if not is_audit_enabled():
        return
    
    user_id = user.id if user and hasattr(user, 'id') else None
    user_display = str(user_id) if user_id else 'anonymous'

    log_context = {
        'event': 'permission_check',
        'action': action,
        'biz_module': module,
        'user_id': user_display,
        'scope': scope,
        'allowed': allowed,
    }

    logger.info(
        f"Permission check: {action} on {module} for user {user_display} | "
        f"scope={scope} | {'ALLOWED' if allowed else 'DENIED'}",
        extra=log_context
    )
    
    #  Debug context with sanitization
    if is_debug_enabled() and extra:
        # Note: extra dict should already be sanitized by caller
        # but we log at debug level to avoid exposing in production
        debug_context = {**log_context, 'debug_context': extra}
        logger.debug("Permission check debug context", extra=debug_context)
    
