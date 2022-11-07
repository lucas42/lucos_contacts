# -*- coding: utf-8 -*-

from django.test import TestCase
from django.core.exceptions import BadRequest
from agents.models import Agent, AgentName, PhoneNumber, EmailAddress, FacebookAccount
from agents.importer import importAgent
from copy import deepcopy


class AgentImporterTest(TestCase):

	def test_invalid_import_data(self):
		def import_bad_data(data, errorMessage):
			with self.assertRaises(BadRequest) as cm:
				importAgent(data)
			self.assertEqual(errorMessage, str(cm.exception))

		import_bad_data({}, "Key 'identifiers' missing")
		import_bad_data({'identifiers': {}}, "Key 'identifiers' isn't an array")
		import_bad_data({'identifiers': 'strawberry'}, "Key 'identifiers' isn't an array")
		import_bad_data({'identifiers': [{'number': '01234'}]}, "Identifier missing 'type'")
		import_bad_data({'identifiers': [{'type':'not-a-thing'}]}, "Unknown identifier type 'not-a-thing'")
		import_bad_data({'identifiers': [{'type': ["phone"]}]}, "Unknown identifier type '['phone']'")
		import_bad_data({'identifiers': [{'type': 'name', 'number': '01234'}]}, "Unknown field 'number'")

	def test_matches_phone_number(self):
		bob = Agent.objects.create()
		PhoneNumber.objects.create(agent=bob, number="01314960937") # Phone number reserved by Ofcom for TV & Radio dramas

		output = importAgent({
				'identifiers': [{
					'type': 'phone',
					'number': '01314960937',
				}],
			})
		self.assertEqual(output["id"], bob.id)
		self.assertEqual(output["existing"], True)
		self.assertEqual(output["updated"], False)


	def test_adds_accounts_idempotently(self):
		clare = Agent.objects.create()
		PhoneNumber.objects.create(agent=clare, number="01314960937") # Phone number reserved by Ofcom for TV & Radio dramas

		importData = {
			'identifiers': [{
				'type': 'email',
				'address': 'clare@example.com',
			},{
				'type': 'phone',
				'number': '01314960937',
			}],
		}

		# First time round should add the email address
		output = importAgent(deepcopy(importData))
		self.assertEqual(output["id"], clare.id)
		self.assertEqual(output["existing"], True)
		self.assertEqual(output["updated"], True)
		self.assertEqual(EmailAddress.objects.filter(agent=clare, address="clare@example.com").count(), 1)

		# Following times should make no changes
		output = importAgent(deepcopy(importData))
		self.assertEqual(output["id"], clare.id)
		self.assertEqual(output["existing"], True)
		self.assertEqual(output["updated"], False)
		self.assertEqual(EmailAddress.objects.filter(agent=clare, address="clare@example.com").count(), 1)

	def test_ignores_duplicate_matches(self):
		alice = Agent.objects.create()
		bob = Agent.objects.create()
		sally = Agent.objects.create()
		PhoneNumber.objects.create(agent=alice, number="01314960937") # Phone number reserved by Ofcom for TV & Radio dramas
		AgentName.objects.create(agent=alice, name="Allie")
		PhoneNumber.objects.create(agent=bob, number="01314960937") # Same phone number as Alice
		AgentName.objects.create(agent=sally, name="Sallie")

		output = importAgent({
				'identifiers': [{
					'type': 'phone',
					'number': '01314960937',
				},{
					'type': 'name',
					'name': 'Sallie',
				}],
			})
		self.assertEqual(output["id"], sally.id)
		self.assertEqual(output["existing"], True)
		self.assertEqual(output["updated"], True)
		self.assertEqual(PhoneNumber.objects.filter(agent=sally, number="01314960937").count(), 1)

	def test_agent_created_for_no_matches(self):
		output = importAgent({
				'identifiers': [{
					'type': 'phone',
					'number': '01314960937', # Phone number reserved by Ofcom for TV & Radio dramas
				}],
			})
		self.assertGreater(output["id"], 0)
		self.assertEqual(output["existing"], False)
		self.assertEqual(output["updated"], True)
		unnamedAgent = Agent.objects.get(pk=output['id'])
		self.assertEqual(PhoneNumber.objects.filter(agent=unnamedAgent, number="01314960937").count(), 1)

	def test_adds_name_idempotently(self):
		philippa = Agent.objects.create()
		PhoneNumber.objects.create(agent=philippa, number="01314960936") # Phone number reserved by Ofcom for TV & Radio dramas

		importData = {
			'identifiers': [{
				'type': 'phone',
				'number': '01314960936',
			},{
				'type': 'name',
				'name': 'Philippa',
			}],
		}

		# First time round should set the name (as primary as there are no other names)
		output = importAgent(deepcopy(importData))
		self.assertEqual(output["id"], philippa.id)
		self.assertEqual(output["existing"], True)
		self.assertEqual(output["updated"], True)
		self.assertEqual(Agent.objects.get(id=philippa.id).getName(), "Philippa")

		# Following times should make no changes
		output = importAgent(deepcopy(importData))
		self.assertEqual(output["id"], philippa.id)
		self.assertEqual(output["existing"], True)
		self.assertEqual(output["updated"], False)
		self.assertEqual(Agent.objects.get(id=philippa.id).getName(), "Philippa")

	def test_updating_field_on_existing_account(self):
		mark = Agent.objects.create()
		FacebookAccount.objects.create(agent=mark, userid="1234", username="old-name") # Phone number reserved by Ofcom for TV & Radio dramas

		output = importAgent({
				'identifiers': [{
					'type': 'facebook',
					'userid': '1234',
					'username': 'new-name',
				}],
			})
		self.assertEqual(output["id"], mark.id)
		self.assertEqual(output["existing"], True)
		self.assertEqual(output["updated"], True)
		self.assertEqual(FacebookAccount.objects.get(agent=mark, userid='1234').username, 'new-name')
