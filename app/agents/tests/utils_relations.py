from django.test import TestCase
from django.utils.translation import gettext as _
from agents.models import Person, Relationship, RomanticRelationship
from agents.utils_relations import get_relationship_info

class RelationshipInfoTest(TestCase):
	def setUp(self):
		self.luke = Person.objects.create(_name="Luke")
		self.leia = Person.objects.create(_name="Leia")

	def test_no_current_agent(self):
		rel_str, priority = get_relationship_info(self.luke, None)
		self.assertEqual(rel_str, '')
		self.assertEqual(priority, -1)

	def test_current_agent_is_self(self):
		rel_str, priority = get_relationship_info(self.luke, self.luke)
		self.assertEqual(rel_str, _('Me'))
		self.assertEqual(priority, -1)

	def test_parent_relationship(self):
		from agents.models.relationshipTypes import lazy_title
		# Luke is parent of Leia
		Relationship.objects.create(subject=self.luke, object=self.leia, relationshipType='parent')
		# get_relationship_info(person, currentagent)
		# Leia's relationship to Luke (currentagent)
		rel_str, priority = get_relationship_info(self.leia, self.luke)
		self.assertEqual(rel_str, lazy_title(_('parent')))
		# Priority for 'parent' is 1 in RELATIONSHIP_TYPE_CHOICES (0 is child, 1 is parent)
		self.assertEqual(priority, 1)

	def test_romantic_personA_active(self):
		# Luke (personA) is in a relationship with Leia (personB)
		RomanticRelationship.objects.create(personA=self.luke, personB=self.leia, active=True, milestone='married')
		rel_str, priority = get_relationship_info(self.leia, self.luke)
		self.assertEqual(rel_str, _('Spouse'))
		self.assertEqual(priority, -1)

	def test_romantic_personB_active(self):
		# Leia (personA) is in a relationship with Luke (personB)
		RomanticRelationship.objects.create(personA=self.leia, personB=self.luke, active=True, milestone='dating')
		rel_str, priority = get_relationship_info(self.leia, self.luke)
		self.assertEqual(rel_str, _('Partner'))
		self.assertEqual(priority, -1)

	def test_romantic_personA_inactive(self):
		RomanticRelationship.objects.create(personA=self.luke, personB=self.leia, active=False, milestone='married')
		rel_str, priority = get_relationship_info(self.leia, self.luke)
		self.assertEqual(rel_str, '')
		self.assertEqual(priority, -1)

	def test_romantic_personB_inactive(self):
		RomanticRelationship.objects.create(personA=self.leia, personB=self.luke, active=False, milestone='dating')
		rel_str, priority = get_relationship_info(self.leia, self.luke)
		self.assertEqual(rel_str, '')
		self.assertEqual(priority, -1)

	def test_multiple_relationships(self):
		from agents.models.relationshipTypes import lazy_title
		# Sibling and Partner
		Relationship.objects.create(subject=self.luke, object=self.leia, relationshipType='sibling')
		# RomanticRelationship.save() reorders personA/personB by ID. 
		# But current agent logic checks both personA and personB related names.
		RomanticRelationship.objects.create(personA=self.luke, personB=self.leia, active=True, milestone='engaged')
		
		rel_str, priority = get_relationship_info(self.leia, self.luke)
		# Order depends on which loop runs first. Sibling (via subject) then Romantic.
		self.assertIn(lazy_title(_('sibling')), rel_str)
		self.assertIn(_('Fiancé'), rel_str)
		self.assertTrue(rel_str.count('/') == 1)
