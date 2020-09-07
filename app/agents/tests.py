# -*- coding: utf-8 -*-
"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""

from django.test import TestCase
from agents.models import *
from agents.relationshipTypes import *

def get_agents_by_relType(subject, relType):
	return [rel.object for rel in Relationship.objects.filter(subject=subject, relationshipType=relType)]

class RelationshipTest(TestCase):

	def test_symmetrical_transitive_relationship(self):
		luke = Agent.objects.create(name_en='Luke')
		rowan = Agent.objects.create(name_en='Rowan')
		roise = Agent.objects.create(name_en='Róise')
		Relationship.objects.create(subject=luke, object=rowan, relationshipType='sibling')
		Relationship.objects.create(subject=rowan, object=roise, relationshipType='sibling')

		self.failUnlessEqual(get_agents_by_relType(luke, 'sibling'), [rowan, roise])
		self.failUnlessEqual(get_agents_by_relType(rowan, 'sibling'), [luke, roise])
		self.failUnlessEqual(get_agents_by_relType(roise, 'sibling'), [luke, rowan])

	def test_transitive_relationship(self):
		luke = Agent.objects.create(name_en='Luke')
		ruth = Agent.objects.create(name_en='Ruth')
		brenda = Agent.objects.create(name_en='Brenda')
		Relationship.objects.create(subject=luke, object=ruth, relationshipType='ancestor')
		Relationship.objects.create(subject=ruth, object=brenda, relationshipType='ancestor')

		self.failUnlessEqual(get_agents_by_relType(luke, 'ancestor'), [ruth, brenda])
		self.failUnlessEqual(get_agents_by_relType(ruth, 'ancestor'), [brenda])
		self.failUnlessEqual(get_agents_by_relType(brenda, 'ancestor'), [])

	def test_symmetrical_relationship(self):
		luke = Agent.objects.create(name_en='Luke')
		james = Agent.objects.create(name_en='James')
		roise = Agent.objects.create(name_en='Róise')
		Relationship.objects.create(subject=luke, object=james, relationshipType='half-sibling')
		Relationship.objects.create(subject=james, object=roise, relationshipType='half-sibling')

		self.failUnlessEqual(get_agents_by_relType(luke, 'half-sibling'), [james])
		self.failUnlessEqual(get_agents_by_relType(james, 'half-sibling'), [luke, roise])
		self.failUnlessEqual(get_agents_by_relType(roise, 'half-sibling'), [james])

	def test_inverse_relationship(self):
		luke = Agent.objects.create(name_en='Luke')
		rachel = Agent.objects.create(name_en='Rachel')
		Relationship.objects.create(subject=luke, object=rachel, relationshipType='aunt/uncle')

		self.failUnlessEqual(get_agents_by_relType(luke, 'aunt/uncle'), [rachel])
		self.failUnlessEqual(get_agents_by_relType(luke, 'nibling'), [])
		self.failUnlessEqual(get_agents_by_relType(rachel, 'aunt/uncle'), [])
		self.failUnlessEqual(get_agents_by_relType(rachel, 'nibling'), [luke])

	def test_inferred_relationship_subject_rel_first(self):
		luke = Agent.objects.create(name_en='Luke')
		mark = Agent.objects.create(name_en='Mark')
		rachel = Agent.objects.create(name_en='Rachel')
		Relationship.objects.create(subject=luke, object=mark, relationshipType='parent')
		Relationship.objects.create(subject=mark, object=rachel, relationshipType='sibling')

		self.failUnlessEqual(get_agents_by_relType(luke, 'aunt/uncle'), [rachel])
		self.failUnlessEqual(get_agents_by_relType(mark, 'aunt/uncle'), [])
		self.failUnlessEqual(get_agents_by_relType(rachel, 'aunt/uncle'), [])

	def test_inferred_relationship_object_rel_first(self):
		luke = Agent.objects.create(name_en='Luke')
		mark = Agent.objects.create(name_en='Mark')
		rachel = Agent.objects.create(name_en='Rachel')
		Relationship.objects.create(subject=mark, object=rachel, relationshipType='sibling')
		Relationship.objects.create(subject=luke, object=mark, relationshipType='parent')

		self.failUnlessEqual(get_agents_by_relType(luke, 'aunt/uncle'), [rachel])
		self.failUnlessEqual(get_agents_by_relType(mark, 'aunt/uncle'), [])
		self.failUnlessEqual(get_agents_by_relType(rachel, 'aunt/uncle'), [])

	def test_complicated_relationship_inference(self):
		luke = Agent.objects.create(name_en='Luke')
		ruth = Agent.objects.create(name_en='Ruth')
		felim = Agent.objects.create(name_en='Felim')
		myra = Agent.objects.create(name_en='Myra')
		brenda = Agent.objects.create(name_en='Brenda')
		frances = Agent.objects.create(name_en='Frances')

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
		parent = Parent("luke", "ruth")
		self.failUnlessEqual(parent.inverse, Child)

	def test_child_relationship(self):
		child = Child("ruth", "luke")
		self.failUnlessEqual(child.inverse, Parent)

	def test_sibling_relationships(self):
		sibling = Sibling("luke", "rowan")
		self.failUnlessEqual(sibling.inverse, Sibling)
