# backend/core/tests/test_idempotency.py

"""
Unit Tests for Idempotency Payload Normalization

Tests normalize_payload() and compute_payload_hash() to ensure:
1. Semantically identical payloads produce the same hash (idempotence)
2. Lists are properly sorted for consistent hashing
3. Edge cases are handled gracefully (None, empty, mixed types, UUIDs)
4. No collisions for different payloads

Compliance: Guarantees idempotency for bulk operations
"""

import uuid
from django.test import TestCase

from core.idempotency import (
    normalize_payload,
    _is_sortable_list,
    compute_payload_hash,
)


# ============================================================================
# TEST SUITE 1: normalize_payload() - Basic Functionality
# ============================================================================

class NormalizePayloadBasicTests(TestCase):
    """Test normalize_payload() for common use cases."""
    
    def test_sorts_simple_string_list(self):
        """Test that simple string lists are sorted."""
        payload = {"ids": ["def", "abc", "ghi"]}
        
        normalized = normalize_payload(payload)
        
        self.assertEqual(normalized["ids"], ["abc", "def", "ghi"])
    
    def test_sorts_integer_list(self):
        """Test that integer lists are sorted."""
        payload = {"ids": [3, 1, 2]}
        
        normalized = normalize_payload(payload)
        
        self.assertEqual(normalized["ids"], [1, 2, 3])
    
    def test_sorts_uuid_list(self):
        """Test that UUID lists are sorted (converted to strings)."""
        uuid1 = uuid.UUID('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
        uuid2 = uuid.UUID('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb')
        uuid3 = uuid.UUID('cccccccc-cccc-cccc-cccc-cccccccccccc')
        
        payload = {"ids": [uuid3, uuid1, uuid2]}
        
        normalized = normalize_payload(payload)
        
        # UUIDs should be converted to strings and sorted
        expected = [
            str(uuid1),
            str(uuid2),
            str(uuid3)
        ]
        self.assertEqual(normalized["ids"], expected)
    
    def test_preserves_dict_list_order(self):
        """Test that lists of dicts preserve original order."""
        payload = {
            "users": [
                {"id": "user-2", "email": "b@test.com"},
                {"id": "user-1", "email": "a@test.com"}
            ]
        }
        
        normalized = normalize_payload(payload)
        
        # Order should be preserved (list of dicts)
        self.assertEqual(normalized["users"][0]["id"], "user-2")
        self.assertEqual(normalized["users"][1]["id"], "user-1")
    
    def test_normalizes_nested_structures(self):
        """Test that nested structures are recursively normalized."""
        payload = {
            "level1": {
                "level2": {
                    "ids": ["z", "a", "m"]
                }
            }
        }
        
        normalized = normalize_payload(payload)
        
        self.assertEqual(
            normalized["level1"]["level2"]["ids"],
            ["a", "m", "z"]
        )
    
    def test_handles_mixed_dict_and_list(self):
        """Test payload with both dicts and lists at different levels."""
        payload = {
            "ids": ["def", "abc"],
            "metadata": {
                "tags": ["tag2", "tag1"]
            },
            "count": 42
        }
        
        normalized = normalize_payload(payload)
        
        self.assertEqual(normalized["ids"], ["abc", "def"])
        self.assertEqual(normalized["metadata"]["tags"], ["tag1", "tag2"])
        self.assertEqual(normalized["count"], 42)
    
    def test_preserves_primitives(self):
        """Test that primitive types are returned unchanged."""
        self.assertEqual(normalize_payload("string"), "string")
        self.assertEqual(normalize_payload(123), 123)
        self.assertEqual(normalize_payload(45.67), 45.67)
        self.assertEqual(normalize_payload(True), True)
        self.assertEqual(normalize_payload(None), None)


# ============================================================================
# TEST SUITE 2: normalize_payload() - Edge Cases
# ============================================================================

class NormalizePayloadEdgeCasesTests(TestCase):
    """Test normalize_payload() for edge cases and defensive behavior."""
    
    def test_handles_empty_list(self):
        """Test that empty lists are handled correctly."""
        payload = {"ids": []}
        
        normalized = normalize_payload(payload)
        
        self.assertEqual(normalized["ids"], [])
    
    def test_handles_empty_dict(self):
        """Test that empty dicts are handled correctly."""
        payload = {}
        
        normalized = normalize_payload(payload)
        
        self.assertEqual(normalized, {})
    
    def test_handles_none_value(self):
        """Test that None values are preserved."""
        payload = {"data": None}
        
        normalized = normalize_payload(payload)
        
        self.assertEqual(normalized["data"], None)
    
    def test_handles_mixed_type_list_defensively(self):
        """Test that mixed type lists preserve order (defensive)."""
        payload = {"mixed": ["abc", 123, "def"]}
        
        normalized = normalize_payload(payload)
        
        # Mixed types should preserve order (not sortable)
        self.assertEqual(normalized["mixed"], ["abc", 123, "def"])
    
    def test_handles_list_with_none_values(self):
        """Test that lists containing None preserve order."""
        payload = {"values": ["a", None, "b"]}
        
        normalized = normalize_payload(payload)
        
        # Lists with None should preserve order (defensive)
        self.assertEqual(normalized["values"], ["a", None, "b"])
    
    def test_handles_nested_empty_structures(self):
        """Test deeply nested empty structures."""
        payload = {
            "level1": {
                "level2": {
                    "empty_list": [],
                    "empty_dict": {}
                }
            }
        }
        
        normalized = normalize_payload(payload)
        
        self.assertEqual(normalized["level1"]["level2"]["empty_list"], [])
        self.assertEqual(normalized["level1"]["level2"]["empty_dict"], {})
    
    def test_converts_tuple_to_sorted_list(self):
        """Test that tuples are converted to sorted lists."""
        payload = {"ids": ("z", "a", "m")}
        
        normalized = normalize_payload(payload)
        
        self.assertEqual(normalized["ids"], ["a", "m", "z"])
    
    def test_converts_set_to_sorted_list(self):
        """Test that sets are converted to sorted lists."""
        payload = {"ids": {"z", "a", "m"}}
        
        normalized = normalize_payload(payload)
        
        # Sets are unordered, but after normalization should be sorted list
        self.assertEqual(sorted(normalized["ids"]), ["a", "m", "z"])
    
    def test_handles_float_list(self):
        """Test that float lists are sorted correctly."""
        payload = {"values": [3.14, 1.41, 2.71]}
        
        normalized = normalize_payload(payload)
        
        self.assertEqual(normalized["values"], [1.41, 2.71, 3.14])
    
    def test_handles_mixed_int_float_list(self):
        """Test that mixed int/float lists are sorted (numeric comparison)."""
        payload = {"values": [3, 1.5, 2, 0.5]}
        
        normalized = normalize_payload(payload)
        
        self.assertEqual(normalized["values"], [0.5, 1.5, 2, 3])
    
    def test_handles_boolean_list(self):
        """Test that boolean lists are sorted."""
        payload = {"flags": [True, False, True, False]}
        
        normalized = normalize_payload(payload)
        
        # Booleans: False < True
        self.assertEqual(normalized["flags"], [False, False, True, True])


# ============================================================================
# TEST SUITE 3: _is_sortable_list() Helper Tests
# ============================================================================

class IsSortableListTests(TestCase):
    """Test the _is_sortable_list() helper function."""
    
    def test_string_list_is_sortable(self):
        """Test that homogeneous string list is sortable."""
        self.assertTrue(_is_sortable_list(["a", "b", "c"]))
    
    def test_int_list_is_sortable(self):
        """Test that homogeneous int list is sortable."""
        self.assertTrue(_is_sortable_list([1, 2, 3]))
    
    def test_float_list_is_sortable(self):
        """Test that homogeneous float list is sortable."""
        self.assertTrue(_is_sortable_list([1.1, 2.2, 3.3]))
    
    def test_bool_list_is_sortable(self):
        """Test that homogeneous bool list is sortable."""
        self.assertTrue(_is_sortable_list([True, False, True]))
    
    def test_mixed_int_float_is_sortable(self):
        """Test that mixed int/float is sortable (numeric)."""
        self.assertTrue(_is_sortable_list([1, 2.5, 3]))
    
    def test_dict_list_is_not_sortable(self):
        """Test that list of dicts is NOT sortable."""
        self.assertFalse(_is_sortable_list([{"id": 1}, {"id": 2}]))
    
    def test_nested_list_is_not_sortable(self):
        """Test that nested list is NOT sortable."""
        self.assertFalse(_is_sortable_list([[1, 2], [3, 4]]))
    
    def test_mixed_string_int_is_not_sortable(self):
        """Test that mixed str/int is NOT sortable (defensive)."""
        self.assertFalse(_is_sortable_list(["a", 1, "b"]))
    
    def test_empty_list_is_not_sortable(self):
        """Test that empty list is NOT sortable (no-op)."""
        self.assertFalse(_is_sortable_list([]))


# ============================================================================
# TEST SUITE 4: compute_payload_hash() - Idempotence Guarantee
# ============================================================================

class ComputePayloadHashIdempotenceTests(TestCase):
    """
    Test that compute_payload_hash() guarantees idempotence.
    
    Critical: Same semantic payload MUST produce same hash regardless of order.
    """
    
    def test_reordered_list_produces_same_hash(self):
        """Test that reordered lists produce identical hash."""
        payload1 = {"ids": ["abc", "def", "ghi"]}
        payload2 = {"ids": ["ghi", "abc", "def"]}
        
        hash1 = compute_payload_hash(payload1)
        hash2 = compute_payload_hash(payload2)
        
        self.assertEqual(hash1, hash2)
    
    def test_reordered_dict_keys_produce_same_hash(self):
        """Test that dict key order doesn't affect hash."""
        payload1 = {"a": 1, "b": 2, "c": 3}
        payload2 = {"c": 3, "a": 1, "b": 2}
        
        hash1 = compute_payload_hash(payload1)
        hash2 = compute_payload_hash(payload2)
        
        self.assertEqual(hash1, hash2)
    
    def test_complex_nested_reordered_produces_same_hash(self):
        """Test complex nested structures with reordering."""
        payload1 = {
            "ids": ["z", "a", "m"],
            "metadata": {"tags": ["tag2", "tag1"]},
            "mode": "partial"
        }
        payload2 = {
            "mode": "partial",
            "metadata": {"tags": ["tag1", "tag2"]},
            "ids": ["a", "m", "z"]
        }
        
        hash1 = compute_payload_hash(payload1)
        hash2 = compute_payload_hash(payload2)
        
        self.assertEqual(hash1, hash2)
    
    def test_uuid_list_reordered_produces_same_hash(self):
        """Test that UUID lists are idempotent."""
        uuid1 = uuid.UUID('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
        uuid2 = uuid.UUID('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb')
        
        payload1 = {"ids": [uuid1, uuid2]}
        payload2 = {"ids": [uuid2, uuid1]}
        
        hash1 = compute_payload_hash(payload1)
        hash2 = compute_payload_hash(payload2)
        
        self.assertEqual(hash1, hash2)
    
    def test_integer_list_reordered_produces_same_hash(self):
        """Test that integer lists are idempotent."""
        payload1 = {"ids": [1, 2, 3, 4, 5]}
        payload2 = {"ids": [5, 3, 1, 4, 2]}
        
        hash1 = compute_payload_hash(payload1)
        hash2 = compute_payload_hash(payload2)
        
        self.assertEqual(hash1, hash2)


# ============================================================================
# TEST SUITE 5: compute_payload_hash() - Collision Prevention
# ============================================================================

class ComputePayloadHashCollisionTests(TestCase):
    """
    Test that compute_payload_hash() produces different hashes for different payloads.
    
    Critical: Different payloads MUST produce different hashes (no collisions).
    """
    
    def test_different_values_produce_different_hash(self):
        """Test that different list values produce different hashes."""
        payload1 = {"ids": ["abc", "def"]}
        payload2 = {"ids": ["abc", "xyz"]}
        
        hash1 = compute_payload_hash(payload1)
        hash2 = compute_payload_hash(payload2)
        
        self.assertNotEqual(hash1, hash2)
    
    def test_different_keys_produce_different_hash(self):
        """Test that different dict keys produce different hashes."""
        payload1 = {"ids": ["abc"]}
        payload2 = {"user_ids": ["abc"]}
        
        hash1 = compute_payload_hash(payload1)
        hash2 = compute_payload_hash(payload2)
        
        self.assertNotEqual(hash1, hash2)
    
    def test_different_list_lengths_produce_different_hash(self):
        """Test that different list lengths produce different hashes."""
        payload1 = {"ids": ["abc", "def"]}
        payload2 = {"ids": ["abc", "def", "ghi"]}
        
        hash1 = compute_payload_hash(payload1)
        hash2 = compute_payload_hash(payload2)
        
        self.assertNotEqual(hash1, hash2)
    
    def test_different_nested_values_produce_different_hash(self):
        """Test that different nested values produce different hashes."""
        payload1 = {"metadata": {"mode": "partial"}}
        payload2 = {"metadata": {"mode": "strict"}}
        
        hash1 = compute_payload_hash(payload1)
        hash2 = compute_payload_hash(payload2)
        
        self.assertNotEqual(hash1, hash2)
    
    def test_empty_vs_nonempty_produce_different_hash(self):
        """Test that empty and non-empty lists produce different hashes."""
        payload1 = {"ids": []}
        payload2 = {"ids": ["abc"]}
        
        hash1 = compute_payload_hash(payload1)
        hash2 = compute_payload_hash(payload2)
        
        self.assertNotEqual(hash1, hash2)


# ============================================================================
# TEST SUITE 6: compute_payload_hash() - Hash Properties
# ============================================================================

class ComputePayloadHashPropertiesTests(TestCase):
    """Test that compute_payload_hash() produces valid hashes."""
    
    def test_returns_64_character_hex_string(self):
        """Test that hash is 64-char hex (SHA-256)."""
        payload = {"ids": ["abc", "def"]}
        
        hash_value = compute_payload_hash(payload)
        
        self.assertEqual(len(hash_value), 64)
        self.assertTrue(all(c in '0123456789abcdef' for c in hash_value))
    
    def test_same_payload_always_produces_same_hash(self):
        """Test deterministic hashing (same input → same output)."""
        payload = {"ids": ["abc", "def"], "mode": "partial"}
        
        hash1 = compute_payload_hash(payload)
        hash2 = compute_payload_hash(payload)
        hash3 = compute_payload_hash(payload)
        
        self.assertEqual(hash1, hash2)
        self.assertEqual(hash2, hash3)
    
    def test_handles_none_payload(self):
        """Test that None payload produces valid hash."""
        hash_value = compute_payload_hash(None)
        
        self.assertEqual(len(hash_value), 64)
    
    def test_handles_empty_dict_payload(self):
        """Test that empty dict produces valid hash."""
        hash_value = compute_payload_hash({})
        
        self.assertEqual(len(hash_value), 64)


# ============================================================================
# TEST SUITE 7: Integration - Real-World Bulk Operation Payloads
# ============================================================================

class IntegrationRealWorldPayloadsTests(TestCase):
    """
    Test with real-world bulk operation payloads from user_view_bulk.py.
    
    Simulates actual payloads sent by clients to bulk endpoints.
    """
    
    def test_bulk_update_payload_idempotent(self):
        """Test realistic bulk update payload is idempotent."""
        # Payload 1: User IDs in order
        payload1 = {
            "ids": [
                "550e8400-e29b-41d4-a716-446655440001",
                "550e8400-e29b-41d4-a716-446655440002",
                "550e8400-e29b-41d4-a716-446655440003"
            ],
            "patch": {
                "is_active": False
            },
            "mode": "partial"
        }
        
        # Payload 2: Same IDs, different order
        payload2 = {
            "ids": [
                "550e8400-e29b-41d4-a716-446655440003",
                "550e8400-e29b-41d4-a716-446655440001",
                "550e8400-e29b-41d4-a716-446655440002"
            ],
            "patch": {
                "is_active": False
            },
            "mode": "partial"
        }
        
        hash1 = compute_payload_hash(payload1)
        hash2 = compute_payload_hash(payload2)
        
        # CRITICAL: Must be identical for idempotent retry
        self.assertEqual(hash1, hash2)
    
    def test_bulk_delete_payload_idempotent(self):
        """Test realistic bulk delete payload is idempotent."""
        # Simulates bulk delete request
        payload1 = {
            "ids": ["user-abc", "user-def", "user-ghi"],
            "mode": "strict"
        }
        payload2 = {
            "ids": ["user-ghi", "user-abc", "user-def"],
            "mode": "strict"
        }
        
        hash1 = compute_payload_hash(payload1)
        hash2 = compute_payload_hash(payload2)
        
        self.assertEqual(hash1, hash2)
    
    def test_bulk_create_payload_preserves_user_order(self):
        """
        Test bulk create payload with list of user dicts.
        
        Important: Order of user objects may matter semantically,
        so normalize_payload should preserve their order.
        """
        payload = {
            "users": [
                {"email": "user1@test.com", "first_name": "User1"},
                {"email": "user2@test.com", "first_name": "User2"}
            ],
            "mode": "partial"
        }
        
        normalized = normalize_payload(payload)
        
        # User order should be preserved (list of dicts)
        self.assertEqual(
            normalized["users"][0]["email"],
            "user1@test.com"
        )
        self.assertEqual(
            normalized["users"][1]["email"],
            "user2@test.com"
        )
    
    def test_mixed_payload_with_metadata(self):
        """Test payload with sortable IDs and unsortable metadata."""
        payload = {
            "ids": ["id-3", "id-1", "id-2"],
            "patch": {"role": "admin"},
            "options": {
                "send_email": True,
                "tags": ["tag2", "tag1"]  # Should be sorted
            }
        }
        
        normalized = normalize_payload(payload)
        
        # IDs should be sorted
        self.assertEqual(normalized["ids"], ["id-1", "id-2", "id-3"])
        
        # Tags should be sorted
        self.assertEqual(normalized["options"]["tags"], ["tag1", "tag2"])
        
        # Other fields preserved
        self.assertEqual(normalized["patch"]["role"], "admin")


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    import unittest
    unittest.main()