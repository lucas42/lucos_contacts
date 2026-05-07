from django.test import TestCase
from django.db import IntegrityError
from comms.models import OccasionList, OccasionType, Present, BirthdayPresent
from agents.models import Person, PersonName


def make_person(name=None):
	person = Person.objects.create()
	if name:
		PersonName.objects.create(agent=person, name=name)
	return person


class OccasionListModelTest(TestCase):
	"""Tests for the OccasionList model."""

	def test_str_includes_year(self):
		occasion = OccasionList.objects.create(type=OccasionType.CHRISTMAS, year=2024)
		text = str(occasion)
		self.assertIn('2024', text)
		self.assertTrue(text)  # non-empty

	def test_unique_together_prevents_duplicate_type_year(self):
		OccasionList.objects.create(type=OccasionType.BIRTHDAY, year=2024)
		with self.assertRaises(IntegrityError):
			OccasionList.objects.create(type=OccasionType.BIRTHDAY, year=2024)

	def test_same_type_different_year_allowed(self):
		OccasionList.objects.create(type=OccasionType.CHRISTMAS, year=2023)
		OccasionList.objects.create(type=OccasionType.CHRISTMAS, year=2024)
		self.assertEqual(OccasionList.objects.count(), 2)

	def test_different_type_same_year_allowed(self):
		OccasionList.objects.create(type=OccasionType.CHRISTMAS, year=2024)
		OccasionList.objects.create(type=OccasionType.BIRTHDAY, year=2024)
		self.assertEqual(OccasionList.objects.count(), 2)


class PresentModelTest(TestCase):
	"""Tests for the Present model."""

	def test_str_includes_description_and_agent(self):
		occasion = OccasionList.objects.create(type=OccasionType.CHRISTMAS, year=2024)
		alice = make_person('Alice')
		present = Present.objects.create(
			occasion=occasion,
			was_given=True,
			description='Handmade Scarf',
		)
		present.agents.add(alice)
		text = str(present)
		self.assertIn('Handmade Scarf', text)
		self.assertIn('Alice', text)

	def test_str_differs_for_given_vs_received(self):
		occasion = OccasionList.objects.create(type=OccasionType.CHRISTMAS, year=2024)
		bob = make_person('Bob')
		given = Present.objects.create(occasion=occasion, was_given=True, description='Scarf')
		received = Present.objects.create(occasion=occasion, was_given=False, description='Book')
		given.agents.add(bob)
		received.agents.add(bob)
		self.assertNotEqual(str(given), str(received))


class BirthdayPresentModelTest(TestCase):
	"""Tests for the BirthdayPresent model."""

	def test_str_includes_description_agent_and_year(self):
		alice = make_person('Alice')
		present = BirthdayPresent.objects.create(
			was_given=True,
			description='Flowers',
			year=2024,
		)
		present.agents.add(alice)
		text = str(present)
		self.assertIn('Flowers', text)
		self.assertIn('Alice', text)
		self.assertIn('2024', text)
