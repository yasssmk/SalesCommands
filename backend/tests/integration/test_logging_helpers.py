# tests/integration/test_logging_helpers.py

"""
Integration Tests for PII-Safe Logging Helpers

Tests the safe_user_context, safe_user_data_context, and safe_batch_context
helpers to ensure they NEVER expose PII in logs.

Compliance: SOC I Type II, GDPR, CCPA
"""

import uuid
from django.test import TestCase
from django.contrib.auth import get_user_model

from core.logging.helpers import (
    safe_user_context,
    safe_user_data_context,
    safe_batch_context,
)

User = get_user_model()


# ============================================================================
# TEST BASE CLASS WITH PROPER SETUP
# ============================================================================

class LoggingHelpersTestCase(TestCase):
    """
    Base test class with proper setup for User creation.
    
    Creates a ClientAccount fixture to satisfy FK constraint on User model.
    """
    
    @classmethod
    def setUpTestData(cls):
        """
        Create test fixtures once for all tests in the class.
        
        This is more efficient than setUp() which runs before each test.
        """
        # Import here to avoid circular imports
        from end_users.models.client_account import ClientAccount
        
        # Create a test client account (required FK for User)
        cls.test_client = ClientAccount.objects.create(
            name='Test Client'
        )
    
    def create_test_user(self, **kwargs):
        """
        Helper to create test users with proper client_account_id.
        
        Args:
            **kwargs: User fields to override
            
        Returns:
            User: Created user instance
        """
        defaults = {
            'client_account': self.test_client,
            'email': f'test_{uuid.uuid4()}@example.com',
            'password': 'testpass123',
            'is_active': True,
            'is_superuser': False
        }
        defaults.update(kwargs)
        
        return User.objects.create_user(**defaults)


# ============================================================================
# TEST SUITE 1: safe_user_context() - Basic Functionality
# ============================================================================

class SafeUserContextTests(LoggingHelpersTestCase):
    """Test safe_user_context() for User instances."""
    
    def test_returns_only_uuid(self):
        """Test that only UUID is returned, no PII."""
        user = self.create_test_user(
            first_name='John',
            last_name='Doe'
        )
        
        context = safe_user_context(user)
        
        # Should ONLY contain safe fields
        self.assertIn('user_id', context)
        self.assertIn('is_active', context)
        self.assertIn('is_superuser', context)
        
        # Should NEVER contain PII
        self.assertNotIn('email', context)
        self.assertNotIn('first_name', context)
        self.assertNotIn('last_name', context)
    
    def test_uuid_format_validation(self):
        """Test that user_id is valid UUID string."""
        user = self.create_test_user()
        
        context = safe_user_context(user)
        user_id = context['user_id']
        
        # Should be valid UUID string
        self.assertIsInstance(user_id, str)
        uuid.UUID(user_id)  # Raises ValueError if invalid
    
    def test_handles_none_user(self):
        """Test that None user returns safe default."""
        context = safe_user_context(None)
        
        self.assertEqual(context, {'user_id': None})
    
    def test_includes_safe_role_flags(self):
        """Test that is_active and is_superuser flags are included."""
        user = self.create_test_user(
            is_active=True,
            is_superuser=False
        )
        
        context = safe_user_context(user)
        
        self.assertEqual(context['is_active'], True)
        self.assertEqual(context['is_superuser'], False)
    
    def test_inactive_user_flag_correctly_set(self):
        """Test that inactive users are flagged correctly."""
        user = self.create_test_user(is_active=False)
        
        context = safe_user_context(user)
        
        self.assertEqual(context['is_active'], False)
    
    def test_superuser_flag_correctly_set(self):
        """Test that superuser flag is correct."""
        user = self.create_test_user(is_superuser=True)
        
        context = safe_user_context(user)
        
        self.assertEqual(context['is_superuser'], True)
    
    def test_includes_role_name_if_available(self):
        """
        Test that role_name is included if present (denormalized field).
        
        Note: role_name is auto-synchronized from role FK in User.save()
        """
        user = self.create_test_user()
        
        # Check if role_name field exists
        if hasattr(user, 'role_name'):
            # Get or create a UserRole to test role_name synchronization
            # Note: Admin role may already exist due to ClientAccount signals
            from end_users.models.role import UserRole
            
            admin_role, created = UserRole.objects.get_or_create(
                name='Admin',
                client_account=self.test_client,
                defaults={
                    'is_admin': True,  # Required by tier constraint
                    'read': True,
                    'write': True,
                    'modify': True,
                    'delete': True
                }
            )
            
            # Assign role - role_name will be auto-synced in save()
            user.role = admin_role
            user.save()
            
            # Reload from DB to get synced value
            user.refresh_from_db()
            
            # Verify helper extracts the synced role_name
            context = safe_user_context(user)
            self.assertEqual(context['role_name'], 'Admin')
        else:
            # If role_name doesn't exist, should be None
            context = safe_user_context(user)
            self.assertEqual(context['role_name'], None)
    
    def test_handles_missing_role_name_gracefully(self):
        """Test that missing role_name doesn't break the helper."""
        user = self.create_test_user()
        
        context = safe_user_context(user)
        
        # Should have role_name key even if None
        self.assertIn('role_name', context)


# ============================================================================
# TEST SUITE 2: safe_user_data_context() - Dict Input
# ============================================================================

class SafeUserDataContextTests(LoggingHelpersTestCase):
    """Test safe_user_data_context() for user data dictionaries."""
    
    def test_extracts_id_from_dict(self):
        """Test that ID is extracted from user_data dict."""
        user_data = {
            'id': 'abc-123-def-456',
            'email': 'test@example.com',  # Should be ignored
            'first_name': 'John'  # Should be ignored
        }
        
        context = safe_user_data_context(user_data)
        
        self.assertEqual(context, {'user_id': 'abc-123-def-456'})
    
    def test_handles_none_input(self):
        """Test that None input returns user_id: None."""
        context = safe_user_data_context(None)
        
        self.assertEqual(context, {'user_id': None})
    
    def test_handles_empty_dict(self):
        """Test that empty dict returns 'pending' (pre-creation state)."""
        context = safe_user_data_context({})
        
        self.assertEqual(context, {'user_id': 'pending'})
    
    def test_handles_dict_without_id(self):
        """Test that dict without 'id' key returns 'pending'."""
        user_data = {
            'email': 'test@example.com',
            'first_name': 'John'
        }
        
        context = safe_user_data_context(user_data)
        
        self.assertEqual(context, {'user_id': 'pending'})
    
    def test_ignores_pii_fields_in_dict(self):
        """Test that PII fields in dict are completely ignored."""
        user_data = {
            'id': 'test-uuid',
            'email': 'sensitive@example.com',
            'first_name': 'Sensitive',
            'last_name': 'Data',
            'phone_number': '+1234567890'
        }
        
        context = safe_user_data_context(user_data)
        
        # Should ONLY return user_id
        self.assertEqual(list(context.keys()), ['user_id'])
        self.assertEqual(context['user_id'], 'test-uuid')


# ============================================================================
# TEST SUITE 3: safe_batch_context() - Batch Operations
# ============================================================================

class SafeBatchContextTests(LoggingHelpersTestCase):
    """Test safe_batch_context() for bulk operations."""
    
    def test_returns_aggregate_stats(self):
        """Test that batch context returns aggregate stats only."""
        users_data = [
            {'id': 'id-1', 'email': 'a@test.com'},
            {'id': 'id-2', 'email': 'b@test.com'},
            {'id': 'id-3', 'email': 'c@test.com'}
        ]
        
        context = safe_batch_context(users_data)
        
        self.assertEqual(context['batch_size'], 3)
        self.assertEqual(context['first_user_id'], 'id-1')
        self.assertEqual(context['last_user_id'], 'id-3')
    
    def test_handles_empty_list(self):
        """Test that empty list returns safe defaults."""
        context = safe_batch_context([])
        
        self.assertEqual(context, {
            'batch_size': 0,
            'first_user_id': None,
            'last_user_id': None
        })
    
    def test_handles_none_input(self):
        """Test that None input returns safe defaults."""
        context = safe_batch_context(None)
        
        self.assertEqual(context, {
            'batch_size': 0,
            'first_user_id': None,
            'last_user_id': None
        })
    
    def test_handles_single_item_list(self):
        """Test that single-item list works correctly."""
        users_data = [{'id': 'single-id', 'email': 'single@test.com'}]
        
        context = safe_batch_context(users_data)
        
        self.assertEqual(context['batch_size'], 1)
        self.assertEqual(context['first_user_id'], 'single-id')
        self.assertEqual(context['last_user_id'], 'single-id')
    
    def test_handles_user_instances_not_just_dicts(self):
        """Test that function works with User instances too."""
        user1 = self.create_test_user()
        user2 = self.create_test_user()
        
        context = safe_batch_context([user1, user2])
        
        self.assertEqual(context['batch_size'], 2)
        self.assertEqual(context['first_user_id'], str(user1.id))
        self.assertEqual(context['last_user_id'], str(user2.id))


# ============================================================================
# TEST SUITE 4: PII Leak Prevention
# ============================================================================

class PIILeakPreventionTests(LoggingHelpersTestCase):
    """
    Critical tests to ensure PII can NEVER leak through helpers.
    
    These tests simulate malicious attempts to inject PII.
    """
    
    def test_cannot_leak_pii_via_string_conversion(self):
        """Test that converting context to string doesn't leak PII."""
        user = self.create_test_user(
            first_name='Sensitive',
            last_name='Data'
        )
        
        context = safe_user_context(user)
        context_str = str(context)
        
        # Should NOT contain any PII
        self.assertNotIn('Sensitive', context_str)
        self.assertNotIn('Data', context_str)
        self.assertNotIn(user.email, context_str)
    
    def test_cannot_inject_pii_via_role_name(self):
        """Test that PII cannot be injected via role_name field."""
        user = self.create_test_user()
        
        # Attempt to inject PII via role_name
        if hasattr(user, 'role_name'):
            # Note: role_name is auto-synced from role FK
            # We can't manually set it, but helper should still not leak PII
            pass
        
        context = safe_user_context(user)
        
        # role_name should be included as-is (it's metadata, not PII)
        # BUT the helper should not extract email from anywhere else
        self.assertNotIn('email', context)
        self.assertNotIn('first_name', context)
    
    def test_cannot_leak_pii_via_dict_keys_iteration(self):
        """Test that iterating over dict keys doesn't expose PII."""
        user = self.create_test_user()
        
        context = safe_user_context(user)
        
        # Iterate all keys - should be safe
        for key in context.keys():
            self.assertNotIn('email', key.lower())
            self.assertNotIn('name', key.lower())
            self.assertNotIn('phone', key.lower())
    
    def test_cannot_leak_pii_via_dict_values_iteration(self):
        """Test that iterating over dict values doesn't expose PII."""
        user = self.create_test_user(
            first_name='Values'
        )
        
        context = safe_user_context(user)
        
        # Iterate all values - should NOT contain PII
        for value in context.values():
            if isinstance(value, str):
                self.assertNotIn(user.email, value)
                if hasattr(user, 'first_name') and user.first_name:
                    self.assertNotIn(user.first_name, value)


# ============================================================================
# TEST SUITE 5: Integration Tests (Real-World Usage)
# ============================================================================

class IntegrationTests(LoggingHelpersTestCase):
    """
    Test real-world usage patterns combining multiple helpers.
    """
    
    def test_real_world_user_update_logging_pattern(self):
        """
        Simulate real user update logging usage.
        """
        user = self.create_test_user(first_name='Update')
        
        # Typical logging pattern in bulk update
        import logging
        logger = logging.getLogger(__name__)
        
        # This is how it should be used in real code
        ctx = {
            'event': 'user_updated',
            'client_id': str(self.test_client.id),
            **safe_user_context(user)  # Spread operator
        }
        
        # Verify context is safe
        self.assertIn('user_id', ctx)
        self.assertIn('event', ctx)
        self.assertNotIn('email', ctx)
        self.assertNotIn('first_name', ctx)
        
        # This would be safe to log
        # logger.info("User updated", extra=ctx)
    
    def test_bulk_operation_logging_pattern(self):
        """
        Simulate bulk operation logging with batch context.
        """
        users = [
            self.create_test_user(),
            self.create_test_user(),
            self.create_test_user()
        ]
        
        # Typical bulk logging pattern
        batch_ctx = safe_batch_context(users)
        
        # Should have aggregate stats only
        self.assertEqual(batch_ctx['batch_size'], 3)
        self.assertIsInstance(batch_ctx['first_user_id'], str)
        self.assertIsInstance(batch_ctx['last_user_id'], str)
        
        # Safe to log
        # logger.info("Bulk operation completed", extra=batch_ctx)
    
    def test_pre_creation_logging_pattern(self):
        """
        Simulate logging before user is created (validation phase).
        """
        # User data from request payload (not yet created)
        user_data = {
            'email': 'new@example.com',  # Will be in DB, but not in logs
            'first_name': 'New'
        }
        
        ctx = safe_user_data_context(user_data)
        
        # Should return 'pending' since no ID yet
        self.assertEqual(ctx['user_id'], 'pending')
        
        # Safe to log validation start
        # logger.info("Starting user validation", extra=ctx)


# ============================================================================
# TEST SUITE 6: Performance Tests (Optional)
# ============================================================================

class PerformanceTests(LoggingHelpersTestCase):
    """
    Optional performance tests for helpers.
    """
    
    def test_helper_is_fast_for_large_batches(self):
        """Test that batch helper is efficient for large batches."""
        import time
        
        # Create 1000 user dicts
        large_batch = [
            {'id': f'id-{i}', 'email': f'user{i}@test.com'}
            for i in range(1000)
        ]
        
        start = time.time()
        context = safe_batch_context(large_batch)
        elapsed = time.time() - start
        
        # Should be < 10ms for 1000 items
        self.assertLess(elapsed, 0.01)
        self.assertEqual(context['batch_size'], 1000)


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    import unittest
    unittest.main()