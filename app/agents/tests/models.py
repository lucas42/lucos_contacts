# -*- coding: utf-8 -*-

from django.test import TestCase, override_settings
from unittest.mock import patch
from agents.models import Person, Relationship
from agents.models.relationship import RelationshipRefusedError, SiblingGroupExpansionRequired
from agents.models.relationshipTypes import Parent, Child, Sibling

def get_agents_by_relType(subject, relType):
	return [rel.object for rel in Relationship.objects.filter(subject=subject, relationshipType=relType)]

class RelationshipTest(TestCase):

	def test_symmetrical_transitive_relationship(self):
		luke = Person.objects.create()
		rowan = Person.objects.create()
		roise = Person.objects.create()
		Relationship.objects.create(subject=luke, object=rowan, relationshipType='sibling')
		Relationship.objects.create(subject=rowan, object=roise, relationshipType='sibling')

		self.assertEqual(get_agents_by_relType(luke, 'sibling'), [rowan, roise])
		self.assertEqual(get_agents_by_relType(rowan, 'sibling'), [luke, roise])
		self.assertEqual(get_agents_by_relType(roise, 'sibling'), [luke, rowan])

	def test_symmetrical_relationship(self):
		luke = Person.objects.create()
		james = Person.objects.create()
		roise = Person.objects.create()
		Relationship.objects.create(subject=luke, object=james, relationshipType='half-sibling')
		Relationship.objects.create(subject=james, object=roise, relationshipType='half-sibling')

		self.assertEqual(get_agents_by_relType(luke, 'half-sibling'), [james])
		self.assertEqual(get_agents_by_relType(james, 'half-sibling'), [luke, roise])
		self.assertEqual(get_agents_by_relType(roise, 'half-sibling'), [james])

	def test_inverse_relationship(self):
		luke = Person.objects.create()
		rachel = Person.objects.create()
		Relationship.objects.create(subject=luke, object=rachel, relationshipType='aunt/uncle')

		self.assertEqual(get_agents_by_relType(luke, 'aunt/uncle'), [rachel])
		self.assertEqual(get_agents_by_relType(luke, 'nibling'), [])
		self.assertEqual(get_agents_by_relType(rachel, 'aunt/uncle'), [])
		self.assertEqual(get_agents_by_relType(rachel, 'nibling'), [luke])

	def test_inferred_relationship_subject_rel_first(self):
		luke = Person.objects.create()
		mark = Person.objects.create()
		rachel = Person.objects.create()
		Relationship.objects.create(subject=luke, object=mark, relationshipType='parent')
		Relationship.objects.create(subject=mark, object=rachel, relationshipType='sibling')

		self.assertEqual(get_agents_by_relType(luke, 'aunt/uncle'), [rachel])
		self.assertEqual(get_agents_by_relType(mark, 'aunt/uncle'), [])
		self.assertEqual(get_agents_by_relType(rachel, 'aunt/uncle'), [])

	def test_inferred_relationship_object_rel_first(self):
		luke = Person.objects.create()
		mark = Person.objects.create()
		rachel = Person.objects.create()
		Relationship.objects.create(subject=mark, object=rachel, relationshipType='sibling')
		Relationship.objects.create(subject=luke, object=mark, relationshipType='parent')

		self.assertEqual(get_agents_by_relType(luke, 'aunt/uncle'), [rachel])
		self.assertEqual(get_agents_by_relType(mark, 'aunt/uncle'), [])
		self.assertEqual(get_agents_by_relType(rachel, 'aunt/uncle'), [])

	def test_complicated_relationship_inference(self):
		luke = Person.objects.create()
		ruth = Person.objects.create()
		felim = Person.objects.create()
		myra = Person.objects.create()
		brenda = Person.objects.create()
		frances = Person.objects.create()

		Relationship.objects.create(subject=luke, object=ruth, relationshipType='parent')
		Relationship.objects.create(subject=ruth, object=felim, relationshipType='sibling')
		Relationship.objects.create(subject=myra, object=felim, relationshipType='sibling')
		Relationship.objects.create(subject=brenda, object=myra, relationshipType='child')
		Relationship.objects.create(subject=frances, object=brenda, relationshipType='sibling')

		self.assertEqual(get_agents_by_relType(luke, 'aunt/uncle'), [felim, myra])
		self.assertCountEqual(get_agents_by_relType(frances, 'nibling'), [myra, ruth, felim])
		self.assertEqual(get_agents_by_relType(luke, 'great aunt/uncle'), [frances])

	def test_prevent_duplicate_relationships(self):
		from django.db import IntegrityError, transaction
		luke = Person.objects.create()
		rowan = Person.objects.create()
		Relationship.objects.create(subject=luke, object=rowan, relationshipType='sibling')
		with self.assertRaises(IntegrityError):
			with transaction.atomic():
				Relationship.objects.create(subject=luke, object=rowan, relationshipType='sibling')
		
		relationships = Relationship.objects.filter(subject=luke, object=rowan, relationshipType='sibling')
		self.assertEqual(relationships.count(), 1)

	def test_merge_removes_duplicate_relationships(self):
		luke = Person.objects.create()
		rowan = Person.objects.create()
		third_person = Person.objects.create()
		Relationship.objects.create(subject=luke, object=third_person, relationshipType='sibling')
		Relationship.objects.create(subject=rowan, object=third_person, relationshipType='sibling')

		from agents.admin import PersonAdmin
		from django.contrib.admin.sites import AdminSite
		from django.test import RequestFactory

		admin = PersonAdmin(Person, AdminSite())
		request = RequestFactory().get('/')
		admin.merge(request, Person.objects.filter(id__in=[luke.id, rowan.id]))

		relationships = Relationship.objects.filter(subject=luke, object=third_person, relationshipType='sibling')
		self.assertEqual(relationships.count(), 1)

	def test_merge_two_agents_transfers_relationships(self):
		"""_merge_two_agents moves secondary's relationships to mainagent and deletes secondary."""
		from agents.admin import PersonAdmin
		from django.contrib.admin.sites import AdminSite

		main_person = Person.objects.create()
		secondary_person = Person.objects.create()
		third_person = Person.objects.create()
		Relationship.objects.create(subject=secondary_person, object=third_person, relationshipType='sibling')

		admin_instance = PersonAdmin(Person, AdminSite())
		admin_instance._merge_two_agents(main_person, secondary_person)

		# secondary should be deleted
		self.assertFalse(Person.objects.filter(pk=secondary_person.pk).exists())
		# main should now have the relationship
		self.assertEqual(
			Relationship.objects.filter(subject=main_person, object=third_person, relationshipType='sibling').count(),
			1,
		)

	def test_merge_two_agents_removes_duplicate_relationships(self):
		"""_merge_two_agents drops duplicate relationships rather than violating the unique constraint."""
		from agents.admin import PersonAdmin
		from django.contrib.admin.sites import AdminSite

		main_person = Person.objects.create()
		secondary_person = Person.objects.create()
		third_person = Person.objects.create()
		Relationship.objects.create(subject=main_person, object=third_person, relationshipType='sibling')
		Relationship.objects.create(subject=secondary_person, object=third_person, relationshipType='sibling')

		admin_instance = PersonAdmin(Person, AdminSite())
		admin_instance._merge_two_agents(main_person, secondary_person)

		self.assertFalse(Person.objects.filter(pk=secondary_person.pk).exists())
		self.assertEqual(
			Relationship.objects.filter(subject=main_person, object=third_person, relationshipType='sibling').count(),
			1,
		)

	def test_merge_two_agents_main_person_survives(self):
		"""The main person always survives; the secondary is deleted."""
		from agents.admin import PersonAdmin
		from django.contrib.admin.sites import AdminSite

		main_person = Person.objects.create()
		secondary_person = Person.objects.create()
		main_id = main_person.pk

		admin_instance = PersonAdmin(Person, AdminSite())
		admin_instance._merge_two_agents(main_person, secondary_person)

		self.assertTrue(Person.objects.filter(pk=main_id).exists())
		self.assertFalse(Person.objects.filter(pk=secondary_person.pk).exists())

class RelationshipTypeTest(TestCase):

	def test_parent_relationship(self):
		parent = Parent()
		self.assertEqual(parent.inverse, Child)

	def test_child_relationship(self):
		child = Child()
		self.assertEqual(child.inverse, Parent)

	def test_sibling_relationships(self):
		sibling = Sibling()
		self.assertEqual(sibling.inverse, Sibling)

class DeathTest(TestCase):
	def test_death_date_sets_is_dead(self):
		jacqui = Person.objects.create()
		jacqui.year_of_death = 2021
		jacqui.save()
		self.assertTrue(jacqui.is_dead)
	def test_is_dead_stays_without_death_date(self):
		jim = Person.objects.create()
		jim.is_dead = True
		jim.save()
		self.assertTrue(jim.is_dead)
	def test_staying_alive(self):
		luke = Person.objects.create()
		luke.is_dead =False
		self.assertFalse(luke.is_dead)


@override_settings(RELATIONSHIP_CLOSURE_CHECK_ENABLED=True)
class RelationshipDeletionSemanticsTest(TestCase):
	"""
	Tests for the closure-check deletion semantics (ADR-0001).
	All tests run with RELATIONSHIP_CLOSURE_CHECK_ENABLED=True.
	"""

	def test_inverse_cascade_on_delete(self):
		"""
		Deleting (A, parent, B) must also delete the inverse (B, child, A).
		Both rows must be absent after the call.
		"""
		alice = Person.objects.create()
		bob = Person.objects.create()
		Relationship.objects.create(subject=alice, object=bob, relationshipType='parent')
		# inference creates the inverse: (bob, child, alice)

		self.assertTrue(
			Relationship.objects.filter(subject=alice, object=bob, relationshipType='parent').exists()
		)
		self.assertTrue(
			Relationship.objects.filter(subject=bob, object=alice, relationshipType='child').exists()
		)

		target = Relationship.objects.get(subject=alice, object=bob, relationshipType='parent')
		target.delete()

		self.assertFalse(
			Relationship.objects.filter(subject=alice, object=bob, relationshipType='parent').exists(),
			"The parent row should be gone",
		)
		self.assertFalse(
			Relationship.objects.filter(subject=bob, object=alice, relationshipType='child').exists(),
			"The inverse child row must also be deleted",
		)

	def test_symmetric_cascade_on_delete(self):
		"""
		Deleting (A, sibling, B) must also delete the symmetric mirror (B, sibling, A).
		"""
		alice = Person.objects.create()
		bob = Person.objects.create()
		Relationship.objects.create(subject=alice, object=bob, relationshipType='sibling')
		# inference creates (bob, sibling, alice)

		target = Relationship.objects.get(subject=alice, object=bob, relationshipType='sibling')
		target.delete()

		self.assertFalse(
			Relationship.objects.filter(subject=alice, object=bob, relationshipType='sibling').exists(),
			"Original sibling row should be gone",
		)
		self.assertFalse(
			Relationship.objects.filter(subject=bob, object=alice, relationshipType='sibling').exists(),
			"Mirror sibling row must also be deleted",
		)

	def test_refused_multi_relation_chain(self):
		"""
		When (A, aunt/uncle, C) is implied by (A, parent, B) + (B, sibling, C),
		attempting to delete the aunt/uncle row must raise RelationshipRefusedError.
		The two supporting rows must remain in the database after the refusal.
		"""
		alice = Person.objects.create()
		bob = Person.objects.create()
		carol = Person.objects.create()

		# alice parent bob → inference creates (bob, child, alice)
		Relationship.objects.create(subject=alice, object=bob, relationshipType='parent')
		# bob sibling carol → inference creates (carol, sibling, bob) and
		# setInference(Parent, Sibling, AuntOrUncle): (alice, aunt/uncle, carol)
		Relationship.objects.create(subject=bob, object=carol, relationshipType='sibling')

		# Verify inference created the aunt/uncle row
		self.assertTrue(
			Relationship.objects.filter(subject=alice, object=carol, relationshipType='aunt/uncle').exists(),
			"Inference should have created alice aunt/uncle carol",
		)

		# Attempt to delete — must be refused
		target = Relationship.objects.get(subject=alice, object=carol, relationshipType='aunt/uncle')
		with self.assertRaises(RelationshipRefusedError) as ctx:
			target.delete()

		# Supporting rows must still exist
		self.assertTrue(
			Relationship.objects.filter(subject=alice, object=bob, relationshipType='parent').exists(),
			"alice→parent→bob must remain",
		)
		self.assertTrue(
			Relationship.objects.filter(subject=bob, object=carol, relationshipType='sibling').exists(),
			"bob→sibling→carol must remain",
		)

		# Error message must mention at least one supporting path
		self.assertIn("can't be removed", str(ctx.exception))

	def test_refused_transitive_sibling(self):
		"""
		With (A, sib, B) + (B, sib, C) transitively implying (A, sib, C),
		attempting to delete (A, sib, C) alone must be refused.
		"""
		alice = Person.objects.create()
		bob = Person.objects.create()
		carol = Person.objects.create()

		Relationship.objects.create(subject=alice, object=bob, relationshipType='sibling')
		Relationship.objects.create(subject=bob, object=carol, relationshipType='sibling')
		# Now (alice, sibling, carol) is transitively inferred

		self.assertTrue(
			Relationship.objects.filter(subject=alice, object=carol, relationshipType='sibling').exists(),
			"Transitive sibling should exist",
		)

		# Attempting to delete the transitive sibling alone must raise
		# SiblingGroupExpansionRequired (the sibling-group expansion can break this)
		target = Relationship.objects.get(subject=alice, object=carol, relationshipType='sibling')
		with self.assertRaises(SiblingGroupExpansionRequired):
			target.delete()

		# The row must still exist — no partial deletion
		self.assertTrue(
			Relationship.objects.filter(subject=alice, object=carol, relationshipType='sibling').exists(),
			"The sibling row must remain after a refused/expansion-required deletion",
		)

	def test_sibling_group_bulk_delete(self):
		"""
		When (A, sib, C) is implied transitively via bob, deleting (A, sib, C)
		alone raises SiblingGroupExpansionRequired.  After the expansion is
		accepted (simulated by calling _perform_staged_deletion with the full
		staged set), all relevant sibling rows are gone and the database is closed.
		"""
		alice = Person.objects.create()
		bob = Person.objects.create()
		carol = Person.objects.create()

		Relationship.objects.create(subject=alice, object=bob, relationshipType='sibling')
		Relationship.objects.create(subject=bob, object=carol, relationshipType='sibling')
		# Transitive: (alice, sibling, carol) now exists

		target = Relationship.objects.get(subject=alice, object=carol, relationshipType='sibling')
		exc = None
		try:
			target.delete()
			self.fail("Expected SiblingGroupExpansionRequired")
		except SiblingGroupExpansionRequired as e:
			exc = e

		# The exception must include all three people's sibling relationships
		# staged_rows should contain all rows connecting alice with bob and carol
		self.assertIsNotNone(exc)
		self.assertIn(
			(alice.pk, carol.pk, 'sibling'),
			exc.staged_rows,
			"Expansion must include the originally targeted row",
		)
		self.assertIn(
			(alice.pk, bob.pk, 'sibling'),
			exc.staged_rows,
			"Expansion must include alice-bob sibling (breaks the transitive chain)",
		)

		# Simulate user confirming: perform the expanded deletion
		target._perform_staged_deletion(exc.staged_rows)

		# All sibling rows for alice must now be gone
		self.assertFalse(
			Relationship.objects.filter(subject=alice, relationshipType='sibling').exists(),
			"alice must have no remaining sibling relationships",
		)
		self.assertFalse(
			Relationship.objects.filter(object=alice, relationshipType='sibling').exists(),
			"No sibling row should point to alice",
		)

	def test_loganne_emissions_on_delete(self):
		"""
		A successful deletion emits one relationshipDeleted event per row in the
		staged set (target + inverse).  A refused deletion emits zero events.
		"""
		alice = Person.objects.create()
		bob = Person.objects.create()
		carol = Person.objects.create()

		# ── Successful deletion: parent+child pair (2 rows → 2 events) ──────
		Relationship.objects.create(subject=alice, object=bob, relationshipType='parent')
		# inverse (bob, child, alice) inferred

		target = Relationship.objects.get(subject=alice, object=bob, relationshipType='parent')

		with patch('agents.loganne.loganneRequest') as mock_loganne:
			with self.captureOnCommitCallbacks(execute=True):
				target.delete()

		# parent + child = 2 rows staged → 2 Loganne calls
		self.assertEqual(
			mock_loganne.call_count,
			2,
			"Expected one Loganne event per deleted row (parent + child inverse)",
		)
		mock_loganne.reset_mock()

		# ── Refused deletion: zero events ────────────────────────────────────
		# Build a scenario that will be refused (transitive sibling expansion
		# will be proposed, which means SiblingGroupExpansionRequired is raised,
		# not RelationshipRefusedError — so check on a multi-relation chain instead)
		Relationship.objects.create(subject=alice, object=carol, relationshipType='parent')
		Relationship.objects.create(subject=carol, object=bob, relationshipType='sibling')
		# Now (alice, aunt/uncle, bob) is inferred

		refused_target = Relationship.objects.get(
			subject=alice, object=bob, relationshipType='aunt/uncle'
		)
		with patch('agents.loganne.loganneRequest') as mock_refused:
			with self.assertRaises(RelationshipRefusedError):
				refused_target.delete()

		self.assertEqual(
			mock_refused.call_count,
			0,
			"A refused deletion must emit no Loganne events",
		)
