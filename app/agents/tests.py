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
		nibling = RelationshipType.objects.create(label_en='nibling')
		nibling.save()
		auntuncle = RelationshipType.objects.create(label_en='aunt/uncle', inverse=nibling)
		auntuncle.save()

		self.failUnlessEqual(nibling.inverse, auntuncle)

		
		luke = Agent.objects.create(name_en='Luke')
		rachel = Agent.objects.create(name_en='Rachel')
		Relationship.objects.create(subject=luke, object=rachel, type=auntuncle)


		self.failUnlessEqual(get_agents_by_relType(luke, auntuncle), [rachel])
		self.failUnlessEqual(get_agents_by_relType(luke, nibling), [])
		self.failUnlessEqual(get_agents_by_relType(rachel, auntuncle), [])
		self.failUnlessEqual(get_agents_by_relType(rachel, nibling), [luke])

	def test_inferred_relationship(self):
		parent = RelationshipType.objects.create(label_en='parent')
		sibling = RelationshipType.objects.create(label_en='sibling')
		auntuncle = RelationshipType.objects.create(label_en='aunt/uncle')

		# The use of a & b seem the wrong way round here, but will keep it like this for now to mantain backwards compatability.  (Need to write a DB migration to change it properly)
		RelationshipTypeConnection.objects.create(relation_type_b=parent, relation_type_a=sibling, inferred_relation_type=auntuncle)

		luke = Agent.objects.create(name_en='Luke')
		mark = Agent.objects.create(name_en='Mark')
		rachel = Agent.objects.create(name_en='Rachel')
		Relationship.objects.create(subject=luke, object=mark, type=parent)
		Relationship.objects.create(subject=mark, object=rachel, type=sibling)

		self.failUnlessEqual(get_agents_by_relType(luke, auntuncle), [rachel])
		self.failUnlessEqual(get_agents_by_relType(mark, auntuncle), [])
		self.failUnlessEqual(get_agents_by_relType(rachel, auntuncle), [])


	def test_inferred_relationship_on_existing_relationships(self):
		parent = RelationshipType.objects.create(label_en='parent')
		sibling = RelationshipType.objects.create(label_en='sibling')
		auntuncle = RelationshipType.objects.create(label_en='aunt/uncle')

		luke = Agent.objects.create(name_en='Luke')
		mark = Agent.objects.create(name_en='Mark')
		rachel = Agent.objects.create(name_en='Rachel')
		Relationship.objects.create(subject=luke, object=mark, type=parent)
		Relationship.objects.create(subject=mark, object=rachel, type=sibling)

		self.failUnlessEqual(get_agents_by_relType(luke, auntuncle), [])

		RelationshipTypeConnection.objects.create(relation_type_b=parent, relation_type_a=sibling, inferred_relation_type=auntuncle)

		self.failUnlessEqual(get_agents_by_relType(luke, auntuncle), [rachel])
		self.failUnlessEqual(get_agents_by_relType(mark, auntuncle), [])
		self.failUnlessEqual(get_agents_by_relType(rachel, auntuncle), [])

	def test_complicated_relationship_inference(self):
		luke = Agent.objects.create(name_en='Luke')
		ruth = Agent.objects.create(name_en='Ruth')
		felim = Agent.objects.create(name_en='Felim')
		myra = Agent.objects.create(name_en='Myra')
		brenda = Agent.objects.create(name_en='Brenda')
		frances = Agent.objects.create(name_en='Frances')


		parent = RelationshipType.objects.create(label_en='parent')
		grandparent = RelationshipType.objects.create(label_en='Grandparent')
		child = RelationshipType.objects.create(label_en='child')
		child.inverse = parent
		child.save()
		grandchild = RelationshipType.objects.create(label_en='child')
		grandchild.inverse = grandparent
		grandchild.save()
		sibling = RelationshipType.objects.create(label_en='sibling')
		sibling.symmetrical = True
		sibling.transitive = True
		sibling.save()
		auntuncle = RelationshipType.objects.create(label_en='aunt/uncle')
		nibling = RelationshipType.objects.create(label_en='nibling')
		auntuncle.inverse = nibling
		auntuncle.save()
		greatauntuncle = RelationshipType.objects.create(label_en='great aunt/uncle')


		RelationshipTypeConnection.objects.create(relation_type_b=sibling, relation_type_a=parent, inferred_relation_type=parent)
		RelationshipTypeConnection.objects.create(relation_type_b=grandparent, relation_type_a=sibling, inferred_relation_type=greatauntuncle)
		RelationshipTypeConnection.objects.create(relation_type_b=parent, relation_type_a=parent, inferred_relation_type=grandparent)

		Relationship.objects.create(subject=luke, object=ruth, type=parent)
		Relationship.objects.create(subject=ruth, object=felim, type=sibling)
		Relationship.objects.create(subject=myra, object=felim, type=sibling)
		Relationship.objects.create(subject=brenda, object=myra, type=child)
		Relationship.objects.create(subject=frances, object=brenda, type=sibling)

		RelationshipTypeConnection.objects.create(relation_type_b=parent, relation_type_a=sibling, inferred_relation_type=auntuncle)


		self.failUnlessEqual(get_agents_by_relType(luke, auntuncle), [felim, myra])
		self.failUnlessEqual(get_agents_by_relType(frances, nibling), [myra, ruth, felim])
		self.failUnlessEqual(get_agents_by_relType(luke, greatauntuncle), [frances])

