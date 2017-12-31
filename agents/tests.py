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

	def test_symmestrical_transitive_relationship(self):
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

	def test_symmestrical_relationship(self):
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