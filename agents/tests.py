# -*- coding: utf-8 -*-
"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""

from django.test import TestCase
from agents.models import *

class SimpleTest(TestCase):
    def test_basic_addition(self):
        """
        Tests that 1 + 1 always equals 2.
        """
        self.failUnlessEqual(1 + 1, 2)

__test__ = {"doctest": """
Another way to test that 1 + 1 is equal to 2.

>>> 1 + 1 == 2
True
"""}

class RelationshipTest(TestCase):
	def test_siblings(self):
		sibling = RelationshipType.objects.create(label_en='sibling')
		sibling.symmetrical = True
		sibling.transitive = True
		sibling.save()
		
		luke = Agent.objects.create(name_en='Luke')
		rowan = Agent.objects.create(name_en='Rowan')
		roise = Agent.objects.create(name_en='Róise')
		Relationship.objects.create(subject=luke, object=rowan, type=sibling)
		Relationship.objects.create(subject=rowan, object=roise, type=sibling)

		self.failUnlessEqual(Relationship.objects.filter(subject=luke).count(), 2)
		self.failUnlessEqual(Relationship.objects.filter(subject=rowan).count(), 2)
		self.failUnlessEqual(Relationship.objects.filter(subject=roise).count(), 2)