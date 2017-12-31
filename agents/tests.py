# -*- coding: utf-8 -*-
"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""

from django.test import TestCase
from agents.models import *

def get_agents_by_relType(subject, relType):
	return [rel.object for rel in Relationship.objects.filter(subject=subject, type=relType)]

class RelationshipTest(TestCase):

	def test_symmetrical_transitive_relationship(self):
		sibling = RelationshipType.objects.create(label_en='sibling')
		sibling.symmetrical = True
		sibling.transitive = True
		sibling.save()
		
		luke = Agent.objects.create(name_en='Luke')
		rowan = Agent.objects.create(name_en='Rowan')
		roise = Agent.objects.create(name_en='Róise')
		Relationship.objects.create(subject=luke, object=rowan, type=sibling)
		Relationship.objects.create(subject=rowan, object=roise, type=sibling)

		self.failUnlessEqual(get_agents_by_relType(luke, sibling), [rowan, roise])
		self.failUnlessEqual(get_agents_by_relType(rowan, sibling), [luke, roise])
		self.failUnlessEqual(get_agents_by_relType(roise, sibling), [luke, rowan])

	def test_transitive_relationship(self):
		ancestor = RelationshipType.objects.create(label_en='sibling')
		ancestor.symmetrical = False
		ancestor.transitive = True
		ancestor.save()
		
		luke = Agent.objects.create(name_en='Luke')
		ruth = Agent.objects.create(name_en='Ruth')
		brenda = Agent.objects.create(name_en='Brenda')
		Relationship.objects.create(subject=luke, object=ruth, type=ancestor)
		Relationship.objects.create(subject=ruth, object=brenda, type=ancestor)

		self.failUnlessEqual(get_agents_by_relType(luke, ancestor), [ruth, brenda])
		self.failUnlessEqual(get_agents_by_relType(ruth, ancestor), [brenda])
		self.failUnlessEqual(get_agents_by_relType(brenda, ancestor), [])

	def test_symmetrical_relationship(self):
		halfsibling = RelationshipType.objects.create(label_en='half sibling')
		halfsibling.symmetrical = True
		halfsibling.transitive = False
		halfsibling.save()
		
		luke = Agent.objects.create(name_en='Luke')
		james = Agent.objects.create(name_en='James')
		roise = Agent.objects.create(name_en='Róise')
		Relationship.objects.create(subject=luke, object=james, type=halfsibling)
		Relationship.objects.create(subject=james, object=roise, type=halfsibling)

		self.failUnlessEqual(get_agents_by_relType(luke, halfsibling), [james])
		self.failUnlessEqual(get_agents_by_relType(james, halfsibling), [luke, roise])
		self.failUnlessEqual(get_agents_by_relType(roise, halfsibling), [james])

	def test_inverse_relationship(self):
		auntuncle = RelationshipType.objects.create(label_en='aunt/uncle')
		nibling = RelationshipType.objects.create(label_en='nibling')
		auntuncle.inverse = nibling
		auntuncle.save()

		self.failUnlessEqual(nibling.inverse, auntuncle)

		
		luke = Agent.objects.create(name_en='Luke')
		rachel = Agent.objects.create(name_en='Rachel')
		Relationship.objects.create(subject=luke, object=rachel, type=auntuncle)


		self.failUnlessEqual(get_agents_by_relType(luke, auntuncle), [rachel])
		self.failUnlessEqual(get_agents_by_relType(luke, nibling), [])
		self.failUnlessEqual(get_agents_by_relType(rachel, auntuncle), [])
		self.failUnlessEqual(get_agents_by_relType(rachel, nibling), [luke])