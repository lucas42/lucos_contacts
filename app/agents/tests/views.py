import json
from datetime import date
from unittest.mock import patch
from django.test import TestCase, Client
from agents.models import Person, PersonName, RomanticRelationship


AUTH_HEADER = {'HTTP_AUTHORIZATION': 'key 1234'}


def make_person(name=None):
	person = Person.objects.create()
	if name:
		PersonName.objects.create(agent=person, name=name)
	return person


class PeopleAllJsonTest(TestCase):
	"""GET /people/all with Accept: application/json returns a JSON list."""

	def setUp(self):
		self.client = Client()

	def test_returns_json_list(self):
		alice = make_person('Alice')
		response = self.client.get(
			'/people/all',
			HTTP_ACCEPT='application/json',
			**AUTH_HEADER,
		)
		self.assertEqual(response.status_code, 200)
		self.assertIn('application/json', response['Content-Type'])
		data = json.loads(response.content)
		self.assertIsInstance(data, list)
		self.assertEqual(len(data), 1)
		self.assertEqual(data[0]['id'], alice.id)
		self.assertEqual(data[0]['name'], 'Alice')
		self.assertIn('url', data[0])

	def test_returns_multiple_people(self):
		make_person('Alice')
		make_person('Bob')
		response = self.client.get(
			'/people/all',
			HTTP_ACCEPT='application/json',
			**AUTH_HEADER,
		)
		self.assertEqual(response.status_code, 200)
		data = json.loads(response.content)
		names = {p['name'] for p in data}
		self.assertIn('Alice', names)
		self.assertIn('Bob', names)

	def test_json_preferred_over_rdf(self):
		"""application/json beats text/turtle when both are in Accept."""
		make_person('Alice')
		response = self.client.get(
			'/people/all',
			HTTP_ACCEPT='application/json, text/turtle;q=0.9',
			**AUTH_HEADER,
		)
		self.assertEqual(response.status_code, 200)
		self.assertIn('application/json', response['Content-Type'])

	def test_rdf_still_works(self):
		"""Existing RDF content negotiation is unaffected."""
		response = self.client.get(
			'/people/all',
			HTTP_ACCEPT='text/turtle',
			**AUTH_HEADER,
		)
		self.assertEqual(response.status_code, 200)
		self.assertIn('text/turtle', response['Content-Type'])

	def test_html_still_works(self):
		"""Default HTML response is unaffected."""
		response = self.client.get(
			'/people/all',
			HTTP_ACCEPT='text/html',
			**AUTH_HEADER,
		)
		self.assertEqual(response.status_code, 200)
		self.assertIn('text/html', response['Content-Type'])

	def test_requires_auth(self):
		response = self.client.get('/people/all', HTTP_ACCEPT='application/json')
		self.assertEqual(response.status_code, 302)  # redirect to login


class PersonDetailJsonTest(TestCase):
	"""GET /people/{id} with Accept: application/json returns a single JSON object."""

	def setUp(self):
		self.client = Client()

	def test_returns_json_object(self):
		alice = make_person('Alice')
		response = self.client.get(
			f'/people/{alice.id}',
			HTTP_ACCEPT='application/json',
			**AUTH_HEADER,
		)
		self.assertEqual(response.status_code, 200)
		self.assertIn('application/json', response['Content-Type'])
		data = json.loads(response.content)
		self.assertEqual(data['id'], alice.id)
		self.assertEqual(data['name'], 'Alice')
		self.assertIn('url', data)

	def test_rdf_still_works(self):
		"""Existing RDF content negotiation is unaffected on individual page."""
		alice = make_person('Alice')
		response = self.client.get(
			f'/people/{alice.id}',
			HTTP_ACCEPT='text/turtle',
			**AUTH_HEADER,
		)
		self.assertEqual(response.status_code, 200)
		self.assertIn('text/turtle', response['Content-Type'])


def make_birthday_person(name, day, month, year=None, starred=False):
	person = Person.objects.create(
		day_of_birth=day, month_of_birth=month, year_of_birth=year, starred=starred,
	)
	PersonName.objects.create(agent=person, name=name)
	return person


def make_deathday_person(name, day, month, year=None, starred=False):
	person = Person.objects.create(
		day_of_death=day, month_of_death=month, year_of_death=year, starred=starred,
	)
	PersonName.objects.create(agent=person, name=name)
	return person


class EventsTodayTest(TestCase):
	"""GET /events/today returns contact events for the current day."""

	def setUp(self):
		self.client = Client()
		# Pin today to 2026-05-06 for all tests in this class
		self.today = date(2026, 5, 6)
		patcher = patch('agents.calendar.date')
		self.mock_date = patcher.start()
		self.mock_date.today.return_value = self.today
		self.mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
		self.addCleanup(patcher.stop)

	def _get(self):
		return self.client.get('/events/today', **AUTH_HEADER)

	def test_returns_empty_list_when_no_events(self):
		response = self._get()
		self.assertEqual(response.status_code, 200)
		self.assertIn('application/json', response['Content-Type'])
		self.assertEqual(json.loads(response.content), [])

	def test_birthday_today_included(self):
		alice = make_birthday_person('Alice', day=6, month=5, year=1990)
		response = self._get()
		data = json.loads(response.content)
		self.assertEqual(len(data), 1)
		event = data[0]
		self.assertEqual(event['type'], 'birthday')
		self.assertEqual(event['person_id'], alice.id)
		self.assertEqual(event['person_name'], 'Alice')
		self.assertEqual(event['person_uri'], f'/people/{alice.id}')
		self.assertIn('Alice', event['label'])
		self.assertIn('36', event['label'])  # age present (language-neutral: "36th" or "36ú")

	def test_birthday_different_day_excluded(self):
		make_birthday_person('Bob', day=7, month=5)
		response = self._get()
		self.assertEqual(json.loads(response.content), [])

	def test_unstarred_birthday_included(self):
		"""No starred filter — unstarred people are included."""
		make_birthday_person('Unstarred', day=6, month=5, starred=False)
		response = self._get()
		data = json.loads(response.content)
		self.assertEqual(len(data), 1)

	def test_starred_birthday_included(self):
		make_birthday_person('Starred', day=6, month=5, starred=True)
		response = self._get()
		data = json.loads(response.content)
		self.assertEqual(len(data), 1)

	def test_birthday_before_birth_year_excluded(self):
		"""Don't show birthday before person is born."""
		make_birthday_person('Future', day=6, month=5, year=2030)
		response = self._get()
		self.assertEqual(json.loads(response.content), [])

	def test_deathday_today_included(self):
		bob = make_deathday_person('Bob', day=6, month=5, year=2020)
		response = self._get()
		data = json.loads(response.content)
		self.assertEqual(len(data), 1)
		event = data[0]
		self.assertEqual(event['type'], 'deathday')
		self.assertEqual(event['person_id'], bob.id)
		self.assertIn('Bob', event['label'])

	def test_anniversary_produces_two_entries(self):
		"""A wedding anniversary produces one entry per person."""
		personA = make_person('Alice')
		personB = make_person('Bob')
		rel = RomanticRelationship.objects.create(
			personA=personA, personB=personB,
			milestone='married', active=True,
			wedding_day=6, wedding_month=5, wedding_year=2010,
		)
		response = self._get()
		data = json.loads(response.content)
		self.assertEqual(len(data), 2)
		types = {e['type'] for e in data}
		self.assertEqual(types, {'anniversary'})
		ids = {e['person_id'] for e in data}
		self.assertIn(personA.id, ids)
		self.assertIn(personB.id, ids)
		# Both entries share the same label
		labels = {e['label'] for e in data}
		self.assertEqual(len(labels), 1)
		self.assertIn('16', list(labels)[0])  # age present (language-neutral: "16th" or "16ú")

	def test_requires_auth(self):
		response = self.client.get('/events/today')
		self.assertEqual(response.status_code, 302)  # redirect to login
