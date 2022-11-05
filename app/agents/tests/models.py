# -*- coding: utf-8 -*-

from django.test import TestCase
from agents.models import Agent, Relationship
from agents.models.relationshipTypes import Parent, Child, Sibling

def get_agents_by_relType(subject, relType):
	return [rel.object for rel in Relationship.objects.filter(subject=subject, relationshipType=relType)]

class RelationshipTest(TestCase):

	def test_symmetrical_transitive_relationship(self):
		luke = Agent.objects.create()
		rowan = Agent.objects.create()
		roise = Agent.objects.create()
		Relationship.objects.create(subject=luke, object=rowan, relationshipType='sibling')
		Relationship.objects.create(subject=rowan, object=roise, relationshipType='sibling')

		self.failUnlessEqual(get_agents_by_relType(luke, 'sibling'), [rowan, roise])
		self.failUnlessEqual(get_agents_by_relType(rowan, 'sibling'), [luke, roise])
		self.failUnlessEqual(get_agents_by_relType(roise, 'sibling'), [luke, rowan])

	def test_symmetrical_relationship(self):
		luke = Agent.objects.create()
		james = Agent.objects.create()
		roise = Agent.objects.create()
		Relationship.objects.create(subject=luke, object=james, relationshipType='half-sibling')
		Relationship.objects.create(subject=james, object=roise, relationshipType='half-sibling')

		self.failUnlessEqual(get_agents_by_relType(luke, 'half-sibling'), [james])
		self.failUnlessEqual(get_agents_by_relType(james, 'half-sibling'), [luke, roise])
		self.failUnlessEqual(get_agents_by_relType(roise, 'half-sibling'), [james])

	def test_inverse_relationship(self):
		luke = Agent.objects.create()
		rachel = Agent.objects.create()
		Relationship.objects.create(subject=luke, object=rachel, relationshipType='aunt/uncle')

		self.failUnlessEqual(get_agents_by_relType(luke, 'aunt/uncle'), [rachel])
		self.failUnlessEqual(get_agents_by_relType(luke, 'nibling'), [])
		self.failUnlessEqual(get_agents_by_relType(rachel, 'aunt/uncle'), [])
		self.failUnlessEqual(get_agents_by_relType(rachel, 'nibling'), [luke])

	def test_inferred_relationship_subject_rel_first(self):
		luke = Agent.objects.create()
		mark = Agent.objects.create()
		rachel = Agent.objects.create()
		Relationship.objects.create(subject=luke, object=mark, relationshipType='parent')
		Relationship.objects.create(subject=mark, object=rachel, relationshipType='sibling')

		self.failUnlessEqual(get_agents_by_relType(luke, 'aunt/uncle'), [rachel])
		self.failUnlessEqual(get_agents_by_relType(mark, 'aunt/uncle'), [])
		self.failUnlessEqual(get_agents_by_relType(rachel, 'aunt/uncle'), [])

	def test_inferred_relationship_object_rel_first(self):
		luke = Agent.objects.create()
		mark = Agent.objects.create()
		rachel = Agent.objects.create()
		Relationship.objects.create(subject=mark, object=rachel, relationshipType='sibling')
		Relationship.objects.create(subject=luke, object=mark, relationshipType='parent')

		self.failUnlessEqual(get_agents_by_relType(luke, 'aunt/uncle'), [rachel])
		self.failUnlessEqual(get_agents_by_relType(mark, 'aunt/uncle'), [])
		self.failUnlessEqual(get_agents_by_relType(rachel, 'aunt/uncle'), [])

	def test_complicated_relationship_inference(self):
		luke = Agent.objects.create()
		ruth = Agent.objects.create()
		felim = Agent.objects.create()
		myra = Agent.objects.create()
		brenda = Agent.objects.create()
		frances = Agent.objects.create()

		Relationship.objects.create(subject=luke, object=ruth, relationshipType='parent')
		Relationship.objects.create(subject=ruth, object=felim, relationshipType='sibling')
		Relationship.objects.create(subject=myra, object=felim, relationshipType='sibling')
		Relationship.objects.create(subject=brenda, object=myra, relationshipType='child')
		Relationship.objects.create(subject=frances, object=brenda, relationshipType='sibling')

		self.failUnlessEqual(get_agents_by_relType(luke, 'aunt/uncle'), [felim, myra])
		self.failUnlessEqual(get_agents_by_relType(frances, 'nibling'), [myra, ruth, felim])
		self.failUnlessEqual(get_agents_by_relType(luke, 'great aunt/uncle'), [frances])

class RelationshipTypeTest(TestCase):

	def test_parent_relationship(self):
		parent = Parent()
		self.failUnlessEqual(parent.inverse, Child)

	def test_child_relationship(self):
		child = Child()
		self.failUnlessEqual(child.inverse, Parent)

	def test_sibling_relationships(self):
		sibling = Sibling()
		self.failUnlessEqual(sibling.inverse, Sibling)

class DeathTest(TestCase):
	def test_death_date_sets_is_dead(self):
		jacqui = Agent.objects.create()
		jacqui.year_of_death = 2021
		jacqui.save()
		self.assertTrue(jacqui.is_dead)
	def test_is_dead_stays_without_death_date(self):
		jim = Agent.objects.create()
		jim.is_dead = True
		jim.save()
		self.assertTrue(jim.is_dead)
	def test_staying_alive(self):
		luke = Agent.objects.create()
		luke.is_dead =False
		self.assertFalse(luke.is_dead)
