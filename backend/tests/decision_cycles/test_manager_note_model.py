# tests/decision_cycles/test_manager_note_model.py
"""
Unit tests for the ManagerNote model.
"""

import pytest

from app_modules.decision_cycles.models import ManagerNote


@pytest.mark.django_db
class TestManagerNoteModel:

    def test_create_note(self, cycle, user_a):
        note = ManagerNote(
            decision_cycle=cycle,
            content='Initial coaching note.',
        )
        note.save(user=user_a, client_id=cycle.client_id)

        assert note.id is not None
        assert note.content == 'Initial coaching note.'
        assert note.decision_cycle_id == cycle.id
        assert note.created_by_id == user_a.id
        assert note.client_id == cycle.client_id

    def test_ordering_newest_first(self, cycle, user_a):
        n1 = ManagerNote(decision_cycle=cycle, content='First')
        n1.save(user=user_a, client_id=cycle.client_id)

        n2 = ManagerNote(decision_cycle=cycle, content='Second')
        n2.save(user=user_a, client_id=cycle.client_id)

        notes = list(ManagerNote.objects.filter(decision_cycle=cycle))
        assert notes[0].id == n2.id
        assert notes[1].id == n1.id

    def test_cascade_delete_with_cycle(self, cycle, user_a):
        note = ManagerNote(decision_cycle=cycle, content='Will be deleted')
        note.save(user=user_a, client_id=cycle.client_id)
        note_id = note.id

        cycle.delete()
        assert not ManagerNote.objects.filter(id=note_id).exists()

    def test_str_representation(self, cycle, user_a):
        note = ManagerNote(decision_cycle=cycle, content='test')
        note.save(user=user_a, client_id=cycle.client_id)
        assert str(user_a.id) in str(note)
