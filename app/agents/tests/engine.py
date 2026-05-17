# -*- coding: utf-8 -*-
"""
Direct unit tests for the relationship inference engine (ADR-0002).

Covers:
  - engine.closure(): ClosureResult.rows and ClosureResult.trace
  - engine.add(): new rows inferred on save
  - engine.plan_deletion(): all three DeletionPlan variants on representative inputs
"""

from django.test import TestCase
from agents.models import Person, Relationship
from agents.models.engine import (
    closure,
    add,
    plan_deletion,
    Safe,
    ExpansionProposed,
    RefusedWithPaths,
    Derivation,
)


class EngineClosureTest(TestCase):
    """Unit tests for engine.closure() — rows and trace."""

    def test_empty_input_returns_empty_result(self):
        result = closure(frozenset())
        self.assertEqual(result.rows, frozenset())
        self.assertEqual(result.trace, {})

    def test_inverse_rule_produces_child_from_parent(self):
        alice = Person.objects.create()
        bob = Person.objects.create()
        rows = frozenset({(alice.pk, bob.pk, 'parent')})
        result = closure(rows)
        self.assertIn((bob.pk, alice.pk, 'child'), result.rows)

    def test_inverse_row_has_trace_entry(self):
        """Derived inverse rows must appear in the trace."""
        alice = Person.objects.create()
        bob = Person.objects.create()
        rows = frozenset({(alice.pk, bob.pk, 'parent')})
        result = closure(rows)
        derived = (bob.pk, alice.pk, 'child')
        self.assertIn(derived, result.trace)
        # At least one derivation records the inverse rule
        self.assertTrue(
            any(d.rule_id.startswith('inverse:') for d in result.trace[derived]),
            "Trace for inverse row must have an inverse rule derivation",
        )

    def test_symmetric_sibling_both_directions(self):
        alice = Person.objects.create()
        bob = Person.objects.create()
        rows = frozenset({(alice.pk, bob.pk, 'sibling')})
        result = closure(rows)
        self.assertIn((bob.pk, alice.pk, 'sibling'), result.rows)

    def test_transitive_sibling_chain(self):
        alice = Person.objects.create()
        bob = Person.objects.create()
        carol = Person.objects.create()
        rows = frozenset({
            (alice.pk, bob.pk, 'sibling'),
            (bob.pk, alice.pk, 'sibling'),
            (bob.pk, carol.pk, 'sibling'),
            (carol.pk, bob.pk, 'sibling'),
        })
        result = closure(rows)
        self.assertIn((alice.pk, carol.pk, 'sibling'), result.rows)
        self.assertIn((carol.pk, alice.pk, 'sibling'), result.rows)

    def test_set_inference_aunt_uncle(self):
        """(A parent B) + (B sibling C) → (A aunt/uncle C)."""
        alice = Person.objects.create()
        bob = Person.objects.create()
        carol = Person.objects.create()
        rows = frozenset({
            (alice.pk, bob.pk, 'parent'),
            (bob.pk, alice.pk, 'child'),
            (bob.pk, carol.pk, 'sibling'),
            (carol.pk, bob.pk, 'sibling'),
        })
        result = closure(rows)
        self.assertIn((alice.pk, carol.pk, 'aunt/uncle'), result.rows)
        self.assertIn((carol.pk, alice.pk, 'nibling'), result.rows)

    def test_no_self_relationship(self):
        """Transitive closure must never produce (A, T, A)."""
        alice = Person.objects.create()
        bob = Person.objects.create()
        rows = frozenset({
            (alice.pk, bob.pk, 'sibling'),
            (bob.pk, alice.pk, 'sibling'),
        })
        result = closure(rows)
        for subj_id, obj_id, _ in result.rows:
            self.assertNotEqual(subj_id, obj_id)

    def test_trace_records_set_inference_derivation(self):
        """Trace must record the two input rows for a setInference-produced row."""
        alice = Person.objects.create()
        bob = Person.objects.create()
        carol = Person.objects.create()
        rows = frozenset({
            (alice.pk, bob.pk, 'parent'),
            (bob.pk, alice.pk, 'child'),
            (bob.pk, carol.pk, 'parent'),
            (carol.pk, bob.pk, 'child'),
        })
        result = closure(rows)
        derived = (alice.pk, carol.pk, 'grandparent')
        self.assertIn(derived, result.rows)
        self.assertIn(derived, result.trace)
        # Find the setinference derivation
        si_derivations = [d for d in result.trace[derived] if 'setinference' in d.rule_id]
        self.assertTrue(si_derivations, "SetInference derivation must be in trace")
        d = si_derivations[0]
        # Input rows must be the two parent facts
        self.assertIn((alice.pk, bob.pk, 'parent'), d.input_rows)
        self.assertIn((bob.pk, carol.pk, 'parent'), d.input_rows)

    def test_input_rows_not_in_trace(self):
        """Rows from the original input must NOT appear as trace keys."""
        alice = Person.objects.create()
        bob = Person.objects.create()
        rows = frozenset({(alice.pk, bob.pk, 'parent')})
        result = closure(rows)
        for row in rows:
            self.assertNotIn(row, result.trace)


class EngineAddTest(TestCase):
    """Unit tests for engine.add()."""

    def test_add_to_empty_set_returns_inverse(self):
        alice = Person.objects.create()
        bob = Person.objects.create()
        new_rows = add((alice.pk, bob.pk, 'parent'), frozenset())
        self.assertIn((bob.pk, alice.pk, 'child'), new_rows)
        # The added row itself must not appear in the result
        self.assertNotIn((alice.pk, bob.pk, 'parent'), new_rows)

    def test_add_sibling_to_existing_sibling_creates_transitive(self):
        alice = Person.objects.create()
        bob = Person.objects.create()
        carol = Person.objects.create()
        existing = frozenset({
            (alice.pk, bob.pk, 'sibling'),
            (bob.pk, alice.pk, 'sibling'),
        })
        new_rows = add((bob.pk, carol.pk, 'sibling'), existing)
        # Transitive: alice-carol and carol-alice should appear
        self.assertIn((alice.pk, carol.pk, 'sibling'), new_rows)
        self.assertIn((carol.pk, alice.pk, 'sibling'), new_rows)
        # Existing rows must not appear
        self.assertNotIn((alice.pk, bob.pk, 'sibling'), new_rows)

    def test_add_returns_frozenset(self):
        alice = Person.objects.create()
        bob = Person.objects.create()
        result = add((alice.pk, bob.pk, 'sibling'), frozenset())
        self.assertIsInstance(result, frozenset)

    def test_add_with_no_new_inferences_returns_empty(self):
        """Saving a symmetric pair that already exists in both directions → empty new_rows."""
        alice = Person.objects.create()
        bob = Person.objects.create()
        existing = frozenset({
            (alice.pk, bob.pk, 'sibling'),
            (bob.pk, alice.pk, 'sibling'),
        })
        # Adding alice-bob-sibling when both directions are already in existing
        new_rows = add((alice.pk, bob.pk, 'sibling'), existing)
        self.assertEqual(new_rows, frozenset())


class EnginePlanDeletionSafeTest(TestCase):
    """Tests for plan_deletion returning Safe."""

    def test_clean_deletion_of_isolated_parent_returns_safe(self):
        """
        Deleting a parent relationship with no re-inference path → Safe.
        """
        alice = Person.objects.create()
        bob = Person.objects.create()
        Relationship.objects.create(subject=alice, object=bob, relationshipType='parent')

        db_rows = frozenset(
            (r.subject_id, r.object_id, r.relationshipType)
            for r in Relationship.objects.all()
        )
        plan = plan_deletion((alice.pk, bob.pk, 'parent'), db_rows)

        self.assertIsInstance(plan, Safe)
        self.assertEqual(plan.kind, 'safe')
        # Staged set must include the target row and its inverse
        self.assertIn((alice.pk, bob.pk, 'parent'), plan.staged)
        self.assertIn((bob.pk, alice.pk, 'child'), plan.staged)

    def test_safe_plan_staged_does_not_contain_unrelated_rows(self):
        alice = Person.objects.create()
        bob = Person.objects.create()
        carol = Person.objects.create()
        Relationship.objects.create(subject=alice, object=bob, relationshipType='parent')
        Relationship.objects.create(subject=alice, object=carol, relationshipType='parent')

        db_rows = frozenset(
            (r.subject_id, r.object_id, r.relationshipType)
            for r in Relationship.objects.all()
        )
        # Delete alice-bob-parent only
        plan = plan_deletion((alice.pk, bob.pk, 'parent'), db_rows)
        self.assertIsInstance(plan, Safe)
        # alice-carol-parent must NOT be staged
        self.assertNotIn((alice.pk, carol.pk, 'parent'), plan.staged)


class EnginePlanDeletionRefusedTest(TestCase):
    """Tests for plan_deletion returning RefusedWithPaths."""

    def test_deletion_refused_when_re_inferred_via_grandparent(self):
        """
        Deleting alice-grandparent-charlie is refused because
        alice-parent-bob + bob-parent-charlie → alice-grandparent-charlie.
        """
        alice = Person.objects.create()
        bob = Person.objects.create()
        charlie = Person.objects.create()
        Relationship.objects.create(subject=alice, object=bob, relationshipType='parent')
        Relationship.objects.create(subject=bob, object=charlie, relationshipType='parent')

        inferred = Relationship.objects.get(
            subject=alice, object=charlie, relationshipType='grandparent'
        )
        db_rows = frozenset(
            (r.subject_id, r.object_id, r.relationshipType)
            for r in Relationship.objects.all()
        )
        plan = plan_deletion((alice.pk, charlie.pk, 'grandparent'), db_rows)

        self.assertIsInstance(plan, RefusedWithPaths)
        self.assertEqual(plan.kind, 'refused')

    def test_refused_plan_paths_not_empty(self):
        """RefusedWithPaths must contain at least one supporting path."""
        alice = Person.objects.create()
        bob = Person.objects.create()
        charlie = Person.objects.create()
        Relationship.objects.create(subject=alice, object=bob, relationshipType='parent')
        Relationship.objects.create(subject=bob, object=charlie, relationshipType='parent')

        db_rows = frozenset(
            (r.subject_id, r.object_id, r.relationshipType)
            for r in Relationship.objects.all()
        )
        plan = plan_deletion((alice.pk, charlie.pk, 'grandparent'), db_rows)
        self.assertIsInstance(plan, RefusedWithPaths)
        self.assertGreater(len(plan.paths), 0, "RefusedWithPaths must have at least one path")

    def test_refused_paths_contain_intermediate_person(self):
        """
        Supporting path for alice-grandparent-charlie must include Bob (the
        intermediate node) as a subject or object in one of its edges.
        """
        alice = Person.objects.create()
        bob = Person.objects.create()
        charlie = Person.objects.create()
        Relationship.objects.create(subject=alice, object=bob, relationshipType='parent')
        Relationship.objects.create(subject=bob, object=charlie, relationshipType='parent')

        db_rows = frozenset(
            (r.subject_id, r.object_id, r.relationshipType)
            for r in Relationship.objects.all()
        )
        plan = plan_deletion((alice.pk, charlie.pk, 'grandparent'), db_rows)
        self.assertIsInstance(plan, RefusedWithPaths)

        # At least one path must contain bob.pk
        found_bob = any(
            bob.pk in (subj_id, obj_id)
            for path in plan.paths
            for subj_id, obj_id, _ in path
        )
        self.assertTrue(found_bob, "Supporting path must reference the intermediate person (Bob)")

    def test_refused_paths_are_grounded_in_remaining_rows(self):
        """All edges in the supporting paths must exist in the remaining graph."""
        alice = Person.objects.create()
        bob = Person.objects.create()
        charlie = Person.objects.create()
        Relationship.objects.create(subject=alice, object=bob, relationshipType='parent')
        Relationship.objects.create(subject=bob, object=charlie, relationshipType='parent')

        db_rows = frozenset(
            (r.subject_id, r.object_id, r.relationshipType)
            for r in Relationship.objects.all()
        )
        target = (alice.pk, charlie.pk, 'grandparent')
        plan = plan_deletion(target, db_rows)
        self.assertIsInstance(plan, RefusedWithPaths)

        remaining = db_rows - plan.staged
        for path in plan.paths:
            for edge in path:
                self.assertIn(
                    edge, remaining,
                    f"Path edge {edge} must be in remaining rows (not in staged set)",
                )


class EnginePlanDeletionExpansionTest(TestCase):
    """Tests for plan_deletion returning ExpansionProposed."""

    def test_sibling_expansion_proposed_for_sibling_row(self):
        """
        Deleting a sibling row that would be re-inferred via transitivity triggers
        ExpansionProposed with reason='sibling_group'.
        """
        alice = Person.objects.create()
        bob = Person.objects.create()
        carol = Person.objects.create()
        # Alice sibling Bob creates Bob sibling Alice (symmetric).
        Relationship.objects.create(subject=alice, object=bob, relationshipType='sibling')
        # Bob sibling Carol creates Carol sibling Bob; transitivity creates Alice sibling Carol.
        Relationship.objects.create(subject=bob, object=carol, relationshipType='sibling')

        db_rows = frozenset(
            (r.subject_id, r.object_id, r.relationshipType)
            for r in Relationship.objects.all()
        )
        plan = plan_deletion((alice.pk, bob.pk, 'sibling'), db_rows)

        self.assertIsInstance(plan, ExpansionProposed)
        self.assertEqual(plan.kind, 'expansion')
        self.assertEqual(plan.reason, 'sibling_group')

    def test_expansion_staged_set_resolves_re_inference(self):
        """The expanded staged set must not be re-inferred from the remaining rows."""
        alice = Person.objects.create()
        bob = Person.objects.create()
        carol = Person.objects.create()
        Relationship.objects.create(subject=alice, object=bob, relationshipType='sibling')
        Relationship.objects.create(subject=bob, object=carol, relationshipType='sibling')

        db_rows = frozenset(
            (r.subject_id, r.object_id, r.relationshipType)
            for r in Relationship.objects.all()
        )
        plan = plan_deletion((alice.pk, bob.pk, 'sibling'), db_rows)
        self.assertIsInstance(plan, ExpansionProposed)

        # After removing plan.staged, the re-inferred check must pass
        remaining = db_rows - plan.staged
        remaining_closure = closure(remaining).rows
        re_inferred = plan.staged & remaining_closure
        self.assertEqual(re_inferred, frozenset(), "Expanded staged set must not be re-inferred")

    def test_sibling_implies_parent_expansion_proposed(self):
        """
        Deleting an inferred parent row (implied by sibling + parent → parent)
        triggers ExpansionProposed with reason='sibling_propagation'.
        """
        carol = Person.objects.create()
        bob = Person.objects.create()
        alice = Person.objects.create()

        # Carol parent Bob (asserted)
        Relationship.objects.create(subject=carol, object=bob, relationshipType='parent')
        # Alice sibling Carol (asserted; infers Alice parent Bob via Sibling+Parent→Parent)
        Relationship.objects.create(subject=alice, object=carol, relationshipType='sibling')

        inferred = Relationship.objects.get(
            subject=alice, object=bob, relationshipType='parent'
        )
        db_rows = frozenset(
            (r.subject_id, r.object_id, r.relationshipType)
            for r in Relationship.objects.all()
        )
        plan = plan_deletion((alice.pk, bob.pk, 'parent'), db_rows)

        self.assertIsInstance(plan, ExpansionProposed)
        self.assertEqual(plan.kind, 'expansion')
        self.assertEqual(plan.reason, 'sibling_propagation')

    def test_expansion_extras_not_empty(self):
        """ExpansionProposed.extras must contain rows beyond the original staged set."""
        alice = Person.objects.create()
        bob = Person.objects.create()
        carol = Person.objects.create()
        Relationship.objects.create(subject=alice, object=bob, relationshipType='sibling')
        Relationship.objects.create(subject=bob, object=carol, relationshipType='sibling')

        db_rows = frozenset(
            (r.subject_id, r.object_id, r.relationshipType)
            for r in Relationship.objects.all()
        )
        plan = plan_deletion((alice.pk, bob.pk, 'sibling'), db_rows)
        self.assertIsInstance(plan, ExpansionProposed)
        self.assertGreater(len(plan.extras), 0, "Extras must be non-empty for expansion")
