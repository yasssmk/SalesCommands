# backend/tests/unit/test_throttle_enforcer.py

"""
Unit tests for dual-key throttle enforcer.

Tests the core logic of check_dual_throttle() including:
- Dual-key enforcement (IP AND email)
- Redis health fallback behavior
- Wait time calculations
- Whitelist handling
- Edge cases (no rate, disabled throttling)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.core.cache import cache
from django.test import RequestFactory
import time

from core.throttle_enforcer import (
    check_dual_throttle,
    reset_throttle,
    _parse_rate,
    _get_client_ip,
    _is_whitelisted,
    _check_single_key,
)

pytestmark = pytest.mark.django_db


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_request():
    """Create a mock request with IP and user."""
    factory = RequestFactory()
    request = factory.post('/login/', {'email': 'test@example.com', 'password': 'pass'})
    request.META['REMOTE_ADDR'] = '203.0.113.10'
    request.user = Mock(is_authenticated=False)
    return request


@pytest.fixture
def throttle_settings(settings):
    """Configure throttle settings for tests."""
    settings.THROTTLING_ENABLED = True
    settings.REST_FRAMEWORK = {
        'DEFAULT_THROTTLE_RATES': {
            'login': '3/minute',
            'test': '5/hour',
        }
    }
    settings.THROTTLE_WHITELIST_IPS = []
    settings.THROTTLE_WHITELIST_USERS = []
    return settings


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before and after each test."""
    cache.clear()
    yield
    cache.clear()


# ============================================================================
# Helper Function Tests
# ============================================================================

class TestHelperFunctions:
    """Test utility functions."""
    
    def test_parse_rate_minute(self):
        """Test parsing rate string with minutes."""
        num, duration = _parse_rate('10/minute')
        assert num == 10
        assert duration == 60
    
    def test_parse_rate_hour(self):
        """Test parsing rate string with hours."""
        num, duration = _parse_rate('5/hour')
        assert num == 5
        assert duration == 3600
    
    def test_parse_rate_day(self):
        """Test parsing rate string with days."""
        num, duration = _parse_rate('100/day')
        assert num == 100
        assert duration == 86400
    
    def test_parse_rate_second(self):
        """Test parsing rate string with seconds."""
        num, duration = _parse_rate('20/second')
        assert num == 20
        assert duration == 1
    
    def test_parse_rate_empty(self):
        """Test parsing empty rate string."""
        num, duration = _parse_rate('')
        assert num == 0
        assert duration == 0
    
    def test_get_client_ip_direct(self, mock_request):
        """Test IP extraction from REMOTE_ADDR."""
        ip = _get_client_ip(mock_request)
        assert ip == '203.0.113.10'
    
    def test_get_client_ip_forwarded(self, mock_request):
        """Test IP extraction from X-Forwarded-For."""
        mock_request.META['HTTP_X_FORWARDED_FOR'] = '198.51.100.5, 203.0.113.10'
        ip = _get_client_ip(mock_request)
        assert ip == '198.51.100.5'  # First IP in chain
    
    def test_get_client_ip_forwarded_single(self, mock_request):
        """Test IP extraction from X-Forwarded-For with single IP."""
        mock_request.META['HTTP_X_FORWARDED_FOR'] = '198.51.100.5'
        ip = _get_client_ip(mock_request)
        assert ip == '198.51.100.5'
    
    def test_is_whitelisted_ip(self, mock_request, settings):
        """Test IP whitelist check."""
        settings.THROTTLE_WHITELIST_IPS = ['203.0.113.10']
        assert _is_whitelisted('203.0.113.10', None, mock_request.user) is True
        assert _is_whitelisted('198.51.100.5', None, mock_request.user) is False
    
    def test_is_whitelisted_email(self, mock_request, settings):
        """Test email whitelist check."""
        settings.THROTTLE_WHITELIST_USERS = ['admin@example.com']
        assert _is_whitelisted('203.0.113.10', 'admin@example.com', mock_request.user) is True
        assert _is_whitelisted('203.0.113.10', 'user@example.com', mock_request.user) is False
    
    def test_is_whitelisted_authenticated_user(self, mock_request, settings):
        """Test authenticated user whitelist check."""
        mock_request.user.is_authenticated = True
        mock_request.user.email = 'admin@example.com'
        settings.THROTTLE_WHITELIST_USERS = ['admin@example.com']
        assert _is_whitelisted('203.0.113.10', None, mock_request.user) is True


# ============================================================================
# Single Key Throttle Tests
# ============================================================================

class TestSingleKeyThrottle:
    """Test _check_single_key() function."""
    
    def test_first_request_not_throttled(self):
        """First request should not be throttled."""
        is_throttled, wait = _check_single_key('test_key_1', 3, 60)
        assert is_throttled is False
        assert wait == 0
    
    def test_within_limit_not_throttled(self):
        """Requests within limit should not be throttled."""
        key = 'test_key_2'
        # Make 2 requests (limit is 3)
        _check_single_key(key, 3, 60)
        is_throttled, wait = _check_single_key(key, 3, 60)
        assert is_throttled is False
        assert wait == 0
    
    def test_exceeds_limit_throttled(self):
        """Requests exceeding limit should be throttled."""
        key = 'test_key_3'
        # Make 3 requests (limit is 3)
        for _ in range(3):
            _check_single_key(key, 3, 60)
        
        # 4th request should be throttled
        is_throttled, wait = _check_single_key(key, 3, 60)
        assert is_throttled is True
        assert wait > 0  # Should have positive wait time
        assert wait <= 60  # Should not exceed duration
    
    def test_wait_time_calculation(self):
        """Wait time should be calculated correctly."""
        key = 'test_key_4'
        duration = 60
        
        # Saturate the limit
        for _ in range(3):
            _check_single_key(key, 3, duration)
        
        # Check wait time
        is_throttled, wait = _check_single_key(key, 3, duration)
        assert is_throttled is True
        # Wait should be approximately equal to duration
        # (with small variance due to execution time)
        assert 55 <= wait <= 60


# ============================================================================
# Dual-Key Throttle Tests
# ============================================================================

class TestDualKeyThrottle:
    """Test check_dual_throttle() main function."""
    
    def test_first_attempt_not_throttled(self, mock_request, throttle_settings):
        """First login attempt should not be throttled."""
        result = check_dual_throttle(mock_request, 'user@example.com', scope='login')
        
        assert result['is_throttled'] is False
        assert result['wait_seconds'] == 0
        assert result['violated_key'] is None
    
    def test_whitelisted_ip_not_throttled(self, mock_request, throttle_settings):
        """Whitelisted IP should bypass throttling."""
        throttle_settings.THROTTLE_WHITELIST_IPS = ['203.0.113.10']
        
        # Saturate limit for this IP
        for _ in range(5):
            check_dual_throttle(mock_request, f'user{_}@example.com', scope='login')
        
        # Should still not be throttled
        result = check_dual_throttle(mock_request, 'another@example.com', scope='login')
        assert result['is_throttled'] is False
        assert result['details']['whitelisted'] is True
    
    def test_whitelisted_email_not_throttled(self, mock_request, throttle_settings):
        """Whitelisted email should bypass throttling."""
        throttle_settings.THROTTLE_WHITELIST_USERS = ['admin@example.com']
        
        # Saturate limit for this email
        for _ in range(5):
            check_dual_throttle(mock_request, 'admin@example.com', scope='login')
        
        # Should still not be throttled
        result = check_dual_throttle(mock_request, 'admin@example.com', scope='login')
        assert result['is_throttled'] is False
        assert result['details']['whitelisted'] is True
    
    def test_ip_limit_exceeded(self, mock_request, throttle_settings):
        """Exceeding IP limit should throttle (even with different emails)."""
        # Rate: 3/minute - make 3 attempts with different emails
        for i in range(3):
            result = check_dual_throttle(
                mock_request, 
                f'user{i}@example.com', 
                scope='login'
            )
            assert result['is_throttled'] is False
        
        # 4th attempt with different email should be throttled (IP limit)
        result = check_dual_throttle(mock_request, 'user99@example.com', scope='login')
        assert result['is_throttled'] is True
        assert result['violated_key'] == 'ip'
        assert result['wait_seconds'] > 0
    
    def test_email_limit_exceeded(self, mock_request, throttle_settings):
        """Exceeding email limit should throttle (even with different IPs)."""
        email = 'target@example.com'
        
        # Rate: 3/minute - make 3 attempts from different IPs
        for i in range(3):
            mock_request.META['REMOTE_ADDR'] = f'203.0.113.{i+10}'
            result = check_dual_throttle(mock_request, email, scope='login')
            assert result['is_throttled'] is False
        
        # 4th attempt from different IP should be throttled (email limit)
        mock_request.META['REMOTE_ADDR'] = '203.0.113.99'
        result = check_dual_throttle(mock_request, email, scope='login')
        assert result['is_throttled'] is True
        assert result['violated_key'] == 'email'
        assert result['wait_seconds'] > 0
    
    def test_both_limits_exceeded_returns_max_wait(self, mock_request, throttle_settings):
        """When both limits exceeded, should return max wait time."""
        email = 'user@example.com'
        
        # Saturate both IP and email limits
        for _ in range(3):
            check_dual_throttle(mock_request, email, scope='login')
        
        # Both should be throttled
        result = check_dual_throttle(mock_request, email, scope='login')
        assert result['is_throttled'] is True
        assert result['wait_seconds'] > 0
        # violated_key could be 'ip' or 'email' depending on which was checked first
        assert result['violated_key'] in ['ip', 'email']
    
    def test_no_rate_configured(self, mock_request, settings):
        """When no rate configured, should allow request."""
        settings.REST_FRAMEWORK = {'DEFAULT_THROTTLE_RATES': {}}
        
        result = check_dual_throttle(mock_request, 'user@example.com', scope='undefined')
        assert result['is_throttled'] is False
        assert result['details']['no_rate_configured'] is True
    
    def test_zero_rate_disables_throttling(self, mock_request, settings):
        """Rate of 0 should disable throttling."""
        settings.REST_FRAMEWORK = {
            'DEFAULT_THROTTLE_RATES': {'login': '0/minute'}
        }
        
        result = check_dual_throttle(mock_request, 'user@example.com', scope='login')
        assert result['is_throttled'] is False
        assert result['details']['throttling_disabled'] is True
    
    def test_case_insensitive_email(self, mock_request, throttle_settings):
        """Email throttling should be case-insensitive."""
        # Make attempts with different case variations
        result1 = check_dual_throttle(mock_request, 'User@Example.Com', scope='login')
        result2 = check_dual_throttle(mock_request, 'user@example.com', scope='login')
        result3 = check_dual_throttle(mock_request, 'USER@EXAMPLE.COM', scope='login')
        
        assert result1['is_throttled'] is False
        assert result2['is_throttled'] is False
        assert result3['is_throttled'] is False
        
        # 4th attempt (same email, different case) should be throttled
        result4 = check_dual_throttle(mock_request, 'uSeR@eXaMpLe.CoM', scope='login')
        assert result4['is_throttled'] is True


# ============================================================================
# Reset Function Tests
# ============================================================================

class TestResetThrottle:
    """Test reset_throttle() function."""
    
    def test_reset_ip_only(self, mock_request, throttle_settings):
        """Test resetting IP throttle counter."""
        ip = '203.0.113.10'
        
        # Saturate IP limit
        for i in range(3):
            check_dual_throttle(mock_request, f'user{i}@example.com', scope='login')
        
        # Verify throttled
        result = check_dual_throttle(mock_request, 'new@example.com', scope='login')
        assert result['is_throttled'] is True
        
        # Reset IP counter
        reset_result = reset_throttle('login', ip=ip)
        assert reset_result['ip_reset'] is True
        assert reset_result['email_reset'] is False
        
        # Should no longer be throttled
        result = check_dual_throttle(mock_request, 'new@example.com', scope='login')
        assert result['is_throttled'] is False
    
    def test_reset_email_only(self, mock_request, throttle_settings):
        """Test resetting email throttle counter."""
        email = 'target@example.com'
        
        # Saturate email limit from different IPs
        for i in range(3):
            mock_request.META['REMOTE_ADDR'] = f'203.0.113.{i+10}'
            check_dual_throttle(mock_request, email, scope='login')
        
        # Verify throttled
        mock_request.META['REMOTE_ADDR'] = '203.0.113.99'
        result = check_dual_throttle(mock_request, email, scope='login')
        assert result['is_throttled'] is True
        
        # Reset email counter
        reset_result = reset_throttle('login', email=email)
        assert reset_result['ip_reset'] is False
        assert reset_result['email_reset'] is True
        
        # Should no longer be throttled
        result = check_dual_throttle(mock_request, email, scope='login')
        assert result['is_throttled'] is False
    
    def test_reset_both(self, mock_request, throttle_settings):
        """Test resetting both IP and email counters."""
        ip = '203.0.113.10'
        email = 'user@example.com'
        
        # Saturate both limits
        for _ in range(3):
            check_dual_throttle(mock_request, email, scope='login')
        
        # Reset both
        reset_result = reset_throttle('login', ip=ip, email=email)
        assert reset_result['ip_reset'] is True
        assert reset_result['email_reset'] is True
        
        # Should no longer be throttled
        result = check_dual_throttle(mock_request, email, scope='login')
        assert result['is_throttled'] is False


# ============================================================================
# Redis Fallback Tests
# ============================================================================

class TestRedisFallback:
    """Test Redis health check and fallback behavior."""
    
    @patch('core.cache_utils._is_redis_backend')
    @patch('core.cache_utils.is_redis_healthy')
    def test_redis_unhealthy_falls_back(
        self, mock_redis_healthy, mock_is_redis, mock_request, throttle_settings
    ):
        """When Redis is unhealthy, should fall back to history-based approach."""
        mock_is_redis.return_value = True
        mock_redis_healthy.return_value = False
        
        # Should still work with file-based cache
        result = check_dual_throttle(mock_request, 'user@example.com', scope='login')
        assert result['is_throttled'] is False
        
        # Make multiple attempts
        for _ in range(3):
            check_dual_throttle(mock_request, 'user@example.com', scope='login')
        
        # Should be throttled even without Redis
        result = check_dual_throttle(mock_request, 'user@example.com', scope='login')
        assert result['is_throttled'] is True
    
    @patch('core.cache_utils._is_redis_backend')
    def test_non_redis_backend_works(
        self, mock_is_redis, mock_request, throttle_settings
    ):
        """Non-Redis backends should work correctly."""
        mock_is_redis.return_value = False
        
        # Should work with file-based cache
        result = check_dual_throttle(mock_request, 'user@example.com', scope='login')
        assert result['is_throttled'] is False