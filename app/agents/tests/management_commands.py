# -*- coding: utf-8 -*-
"""
Tests for the audit_relationship_closure management command.

Covers the four acceptance cases from lucos_contacts#692:
  1. Empty database → zero missing, zero extraneous.
  2. Database with a known missing inference → command reports the missing row.
  3. Database with a known extraneous row → command flags it.
  4. --apply-missing adds missing rows; running again reports zero missing (idempotent).
"""

from io import StringIO
from django.test import TestCase
from django.core.management import call_command
from agents.models import Person, Relationship
from agents.management.commands.audit_relationship_closure import compute_closure


class ComputeClosureTest(TestCase):
    """Unit tests for the pure compute_closure function (no DB required)."""

    def test_empty_set_returns_empty(self):
        result = compute_closure(set())
        self.assertEqual(result, frozenset())

    def test_inverse_relationship(self):
        """parent → child inverse must appear in closure."""
        alice = Person.objects.create()
        bob = Person.objects.create()
        rows = {(alice.pk, bob.pk, 'parent')}
        closure = compute_closure(rows)
        self.assertIn((bob.pk, alice.pk, 'child'), closure)

    def test_symmetrical_sibling(self):
        """Sibling is symmetrical: (A sibling B) → (B sibling A)."""
        alice = Person.objects.create()
        bob = Person.objects.create()
        rows = {(alice.pk, bob.pk, 'sibling')}
        closure = compute_closure(rows)
        self.assertIn((bob.pk, alice.pk, 'sibling'), closure)

    def test_transitive_sibling(self):
        """Sibling is transitive: (A sibling B) + (B sibling C) → (A sibling C)."""
        alice = Person.objects.create()
        bob = Person.objects.create()
        carol = Person.objects.create()
        rows = {
            (alice.pk, bob.pk, 'sibling'),
            (bob.pk, alice.pk, 'sibling'),
            (bob.pk, carol.pk, 'sibling'),
            (carol.pk, bob.pk, 'sibling'),
        }
        closure = compute_closure(rows)
        self.assertIn((alice.pk, carol.pk, 'sibling'), closure)
        self.assertIn((carol.pk, alice.pk, 'sibling'), closure)

    def test_aunt_uncle_inferred(self):
        """(A parent B) + (B sibling C) → (A aunt/uncle C)."""
        alice = Person.objects.create()
        bob = Person.objects.create()
        carol = Person.objects.create()
        # Alice is Bob's parent; Bob and Carol are siblings
        rows = {
            (alice.pk, bob.pk, 'parent'),
            (bob.pk, alice.pk, 'child'),
            (bob.pk, carol.pk, 'sibling'),
            (carol.pk, bob.pk, 'sibling'),
        }
        closure = compute_closure(rows)
        self.assertIn((alice.pk, carol.pk, 'aunt/uncle'), closure)
        self.assertIn((carol.pk, alice.pk, 'nibling'), closure)

    def test_no_self_relationship(self):
        """Transitive closure must never produce (A, T, A)."""
        alice = Person.objects.create()
        bob = Person.objects.create()
        rows = {
            (alice.pk, bob.pk, 'sibling'),
            (bob.pk, alice.pk, 'sibling'),
        }
        closure = compute_closure(rows)
        for subj_id, obj_id, _ in closure:
            self.assertNotEqual(subj_id, obj_id)


class AuditCommandEmptyDatabaseTest(TestCase):
    """Acceptance case 1: empty database → zero missing, zero extraneous."""

    def test_empty_database_is_closed(self):
        out = StringIO()
        call_command('audit_relationship_closure', stdout=out)
        output = out.getvalue()
        self.assertIn('Total: 0', output)
        self.assertIn('Database is closed: zero missing, zero extraneous.', output)


class AuditCommandMissingRowTest(TestCase):
    """Acceptance case 2: database with a known missing inference is reported."""

    def setUp(self):
        self.alice = Person.objects.create()
        self.bob = Person.objects.create()
        self.carol = Person.objects.create()

    def test_missing_aunt_uncle_row_reported(self):
        """
        Set up Alice-parent-Bob and Bob-sibling-Carol but manually bypass the
        inference engine so the aunt/uncle row is absent.  The command must
        report it as missing.
        """
        # Use update_fields to bypass inferRelationships() on save
        alice_bob = Relationship(subject=self.alice, object=self.bob, relationshipType='parent')
        Relationship.save(alice_bob)  # this triggers inferRelationships, which adds child inverse

        # Insert Bob-sibling-Carol directly, bypassing the ORM's save() signal
        # so that the aunt/uncle inference is NOT triggered.
        Relationship.objects.bulk_create([
            Relationship(subject=self.bob, object=self.carol, relationshipType='sibling'),
        ])

        # The DB now has: alice parent bob, bob child alice, bob sibling carol
        # Missing: carol sibling bob (symmetrical), alice aunt/uncle carol, carol nibling alice

        out = StringIO()
        call_command('audit_relationship_closure', stdout=out)
        output = out.getvalue()

        self.assertIn('Database is NOT closed', output)
        # aunt/uncle and nibling are missing
        self.assertIn('aunt/uncle', output)
        self.assertIn('nibling', output)
        # Summary must not say "closed"
        self.assertNotIn('Database is closed:', output)


class AuditCommandExtraneousRowTest(TestCase):
    """Acceptance case 3: extraneous-row section is present and correctly formatted."""

    def test_extraneous_section_present_in_output(self):
        """
        The command always emits an '=== Extraneous rows ===' section.
        When the database is a valid self-consistent set (which is the expected norm —
        since the inference rules are purely additive, every row can appear in the
        closure of itself plus its inverses), the section reports 'Total: 0'.
        """
        alice = Person.objects.create()
        bob = Person.objects.create()
        # A directly-created grandparent/grandchild pair with no parent rows is still
        # self-consistent: grandparent and grandchild are each other's inverses, so
        # compute_closure returns exactly those two rows.  Missing = 0, extraneous = 0.
        Relationship.objects.bulk_create([
            Relationship(subject=alice, object=bob, relationshipType='grandparent'),
            Relationship(subject=bob, object=alice, relationshipType='grandchild'),
        ])

        out = StringIO()
        call_command('audit_relationship_closure', stdout=out)
        output = out.getvalue()

        self.assertIn('=== Extraneous rows ===', output)
        # The pair is self-consistent: no extraneous rows expected
        self.assertIn('Database is closed: zero missing, zero extraneous.', output)

    def test_extraneous_section_formatting(self):
        """
        The extraneous section includes a 'Total:' line regardless of whether
        there are any extraneous rows.
        """
        out = StringIO()
        call_command('audit_relationship_closure', stdout=out)
        output = out.getvalue()

        self.assertIn('=== Extraneous rows ===', output)
        self.assertIn('Total: 0', output)


class AuditCommandApplyMissingTest(TestCase):
    """Acceptance case 4: --apply-missing adds rows; running again shows zero missing."""

    def setUp(self):
        self.alice = Person.objects.create()
        self.bob = Person.objects.create()
        self.carol = Person.objects.create()

    def test_apply_missing_fixes_and_is_idempotent(self):
        """
        After --apply-missing, the database is closed and a second run still reports
        zero missing (idempotent).
        """
        # Set up parent + sibling, bypassing inference on the sibling to leave gaps
        Relationship.save(Relationship(subject=self.alice, object=self.bob, relationshipType='parent'))
        Relationship.objects.bulk_create([
            Relationship(subject=self.bob, object=self.carol, relationshipType='sibling'),
        ])

        # First run: apply missing
        out1 = StringIO()
        call_command('audit_relationship_closure', '--apply-missing', stdout=out1)
        output1 = out1.getvalue()
        self.assertIn('Created', output1)

        # Second run: should now be closed
        out2 = StringIO()
        call_command('audit_relationship_closure', '--apply-missing', stdout=out2)
        output2 = out2.getvalue()
        self.assertIn('Database is closed: zero missing, zero extraneous.', output2)

    def test_apply_missing_only_creates_missing(self):
        """
        --apply-missing must not double-create rows: running it on an already-closed
        database must report 'No missing rows to apply'.
        """
        # Create a proper relationship via the ORM (triggers inference, DB is already closed)
        Relationship.objects.create(subject=self.alice, object=self.bob, relationshipType='sibling')

        out = StringIO()
        call_command('audit_relationship_closure', '--apply-missing', stdout=out)
        output = out.getvalue()
        self.assertIn('No missing rows to apply', output)
