import json
from django.test import TestCase, Client
from agents.models import Person, PersonName


AUTH_HEADER = {'HTTP_AUTHORIZATION': 'key 1234'}

# Calendar key set by CLIENT_KEYS=external_calendar:test=1234 in the test environment.
CALENDAR_KEY = '1234'


def make_person(name=None):
	person = Person.objects.create()
	if name:
		PersonName.objects.create(agent=person, name=name)
	return person


class InfoEndpointTest(TestCase):
	"""Tests for the /_info endpoint."""

	def setUp(self):
		self.client = Client()

	def test_returns_200(self):
		response = self.client.get('/_info')
		self.assertEqual(response.status_code, 200)

	def test_returns_json_content_type(self):
		response = self.client.get('/_info')
		self.assertIn('application/json', response['Content-Type'])

	def test_response_contains_system_name(self):
		response = self.client.get('/_info')
		data = json.loads(response.content)
		self.assertEqual(data['system'], 'lucos_contacts')

	def test_response_contains_checks_and_metrics(self):
		response = self.client.get('/_info')
		data = json.loads(response.content)
		self.assertIn('checks', data)
		self.assertIn('metrics', data)

	def test_accessible_without_authentication(self):
		"""/_info must be reachable without auth — used by monitoring."""
		response = self.client.get('/_info')
		self.assertNotEqual(response.status_code, 302)


class CalendarIcsEndpointTest(TestCase):
	"""Tests for the /calendar.ics HTTP endpoint."""

	def setUp(self):
		self.client = Client()

	def test_returns_200_with_valid_key(self):
		response = self.client.get(f'/calendar.ics?key={CALENDAR_KEY}')
		self.assertEqual(response.status_code, 200)

	def test_returns_text_calendar_content_type(self):
		response = self.client.get(f'/calendar.ics?key={CALENDAR_KEY}')
		self.assertIn('text/calendar', response['Content-Type'])

	def test_body_contains_vcalendar_envelope(self):
		response = self.client.get(f'/calendar.ics?key={CALENDAR_KEY}')
		self.assertIn(b'BEGIN:VCALENDAR', response.content)
		self.assertIn(b'END:VCALENDAR', response.content)

	def test_invalid_key_returns_403(self):
		response = self.client.get('/calendar.ics?key=badkey')
		self.assertEqual(response.status_code, 403)

	def test_no_key_redirects_to_login(self):
		response = self.client.get('/calendar.ics')
		self.assertEqual(response.status_code, 302)
		self.assertIn('/accounts/login', response['Location'])


class ContentNegotiationTest(TestCase):
	"""Tests that a single person URL returns the correct format for each Accept header."""

	def setUp(self):
		self.client = Client()
		self.person = make_person('Alice')

	def _get(self, accept):
		return self.client.get(
			f'/people/{self.person.id}',
			HTTP_ACCEPT=accept,
			**AUTH_HEADER,
		)

	def test_html_accept_returns_html(self):
		response = self._get('text/html')
		self.assertEqual(response.status_code, 200)
		self.assertIn('text/html', response['Content-Type'])

	def test_rdf_accept_returns_rdf(self):
		response = self._get('text/turtle')
		self.assertEqual(response.status_code, 200)
		self.assertIn('text/turtle', response['Content-Type'])

	def test_json_accept_returns_json(self):
		response = self._get('application/json')
		self.assertEqual(response.status_code, 200)
		self.assertIn('application/json', response['Content-Type'])

	def test_default_accept_returns_html(self):
		"""Without an explicit Accept header, HTML is the default."""
		response = self.client.get(
			f'/people/{self.person.id}',
			**AUTH_HEADER,
		)
		self.assertEqual(response.status_code, 200)
		self.assertIn('text/html', response['Content-Type'])
