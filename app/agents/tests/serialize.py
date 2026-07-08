# -*- coding: utf-8 -*-

from django.test import TestCase
from agents.models import Person, EmailAddress
from agents.serialize import serializePerson


class SerializePersonPrimaryEmailTest(TestCase):

	def test_primary_email_present_when_set(self):
		alice = Person.objects.create()
		EmailAddress.objects.create(agent=alice, address='alice@example.com')

		data = serializePerson(agent=alice)

		self.assertEqual(data['primary_email'], 'alice@example.com')
		self.assertEqual(data['email'], ['alice@example.com'])

	def test_primary_email_null_when_no_email(self):
		alice = Person.objects.create()

		data = serializePerson(agent=alice)

		self.assertIsNone(data['primary_email'])
		self.assertEqual(data['email'], [])

	def test_primary_email_reflects_designated_primary(self):
		alice = Person.objects.create()
		EmailAddress.objects.create(agent=alice, address='old@example.com')
		newest = EmailAddress.objects.create(agent=alice, address='new@example.com')
		newest.is_primary = True
		newest.save()

		data = serializePerson(agent=alice)

		self.assertEqual(data['primary_email'], 'new@example.com')
		# The unchanged `email` array still lists every active address.
		self.assertEqual(sorted(data['email']), ['new@example.com', 'old@example.com'])

	def test_primary_email_excludes_inactive_addresses(self):
		alice = Person.objects.create()
		primary = EmailAddress.objects.create(agent=alice, address='alice@example.com')
		primary.active = False
		primary.save()

		data = serializePerson(agent=alice)

		self.assertIsNone(data['primary_email'])
		self.assertEqual(data['email'], [])
