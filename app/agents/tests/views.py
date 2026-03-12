import json
from django.test import TestCase, Client
from agents.models import Person, PersonName


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
