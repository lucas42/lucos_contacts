import io
import json
import urllib.error
from unittest.mock import patch
from django.test import TestCase, Client
from django.contrib.auth.models import User
from lucosauth.models import LucosAuthBackend, LucosUser
from agents.models import Person


AUTH_HEADER = {'HTTP_AUTHORIZATION': 'bearer 1234'}


def json_urlopen_response(data):
	"""Return a BytesIO that json.load() can read, simulating a urllib urlopen response."""
	return io.BytesIO(json.dumps(data).encode())


class ApiAuthDecoratorTest(TestCase):
	"""Tests for the api_auth decorator behaviour.

	Uses /people/all (which is decorated with @api_auth + @login_required)
	as a representative endpoint.
	"""

	def setUp(self):
		self.client = Client()

	def test_invalid_key_returns_403(self):
		"""A request with a recognised-but-wrong key is rejected with 403."""
		response = self.client.get(
			'/people/all',
			HTTP_AUTHORIZATION='bearer wrongkey',
			HTTP_ACCEPT='application/json',
		)
		self.assertEqual(response.status_code, 403)

	def test_no_auth_header_redirects_to_login(self):
		"""No auth header falls through to @login_required, which redirects."""
		response = self.client.get('/people/all', HTTP_ACCEPT='application/json')
		self.assertEqual(response.status_code, 302)
		self.assertIn('/accounts/login', response['Location'])

	def test_valid_key_allows_access(self):
		"""A valid API key grants access to a protected endpoint."""
		response = self.client.get(
			'/people/all',
			HTTP_ACCEPT='application/json',
			**AUTH_HEADER,
		)
		self.assertEqual(response.status_code, 200)


class LucosAuthBackendTest(TestCase):
	"""Tests for LucosAuthBackend — the session-cookie auth flow.

	authenticate() calls the auth service with the token from the session
	cookie, then finds or creates the matching Person and LucosUser.
	"""

	def setUp(self):
		self.backend = LucosAuthBackend()

	@patch('urllib.request.urlopen')
	def test_authenticate_returns_none_on_http_error(self, mock_urlopen):
		"""HTTPError from the auth server (e.g. 403/404) causes authenticate() to return None."""
		mock_urlopen.side_effect = urllib.error.HTTPError(
			'https://auth.l42.eu/data?token=bad', 403, 'Forbidden', {}, None
		)
		result = self.backend.authenticate(None, token='bad-token')
		self.assertIsNone(result)

	@patch('urllib.request.urlopen')
	def test_authenticate_returns_none_on_network_error(self, mock_urlopen):
		"""URLError (network failure, DNS miss) causes authenticate() to return None."""
		mock_urlopen.side_effect = urllib.error.URLError('Connection refused')
		result = self.backend.authenticate(None, token='unreachable-token')
		self.assertIsNone(result)

	@patch('urllib.request.urlopen')
	def test_authenticate_returns_none_when_id_is_null(self, mock_urlopen):
		"""An id=null response from the auth server means no authenticated user."""
		mock_urlopen.return_value = json_urlopen_response({'id': None})
		result = self.backend.authenticate(None, token='null-id-token')
		self.assertIsNone(result)

	@patch('urllib.request.urlopen')
	def test_authenticate_creates_person_and_lucos_user_for_new_id(self, mock_urlopen):
		"""In a non-production environment, authenticate() creates a Person and LucosUser
		when the auth server returns an id not yet in the database."""
		mock_urlopen.return_value = json_urlopen_response({'id': 9001})
		self.assertFalse(Person.objects.filter(id=9001).exists())

		user = self.backend.authenticate(None, token='new-person-token')

		self.assertIsNotNone(user)
		self.assertIsInstance(user, LucosUser)
		person = Person.objects.get(id=9001)
		self.assertEqual(user.agent, person)

	@patch('urllib.request.urlopen')
	def test_authenticate_reuses_existing_person(self, mock_urlopen):
		"""If the Person already exists, authenticate() links to it rather than
		creating a duplicate."""
		person = Person.objects.create(id=9002)
		mock_urlopen.return_value = json_urlopen_response({'id': 9002})

		user = self.backend.authenticate(None, token='existing-person-token')

		self.assertIsNotNone(user)
		self.assertEqual(user.agent, person)
		self.assertEqual(Person.objects.filter(id=9002).count(), 1)

	@patch('urllib.request.urlopen')
	def test_authenticate_reuses_existing_lucos_user(self, mock_urlopen):
		"""If a LucosUser already exists for the Person, authenticate() returns it
		without creating a duplicate."""
		person = Person.objects.create(id=9003)
		existing_user = LucosUser.objects.create(agent=person)
		mock_urlopen.return_value = json_urlopen_response({'id': 9003})

		result = self.backend.authenticate(None, token='existing-user-token')

		self.assertIsNotNone(result)
		self.assertEqual(result.pk, existing_user.pk)
		self.assertEqual(LucosUser.objects.filter(agent=person).count(), 1)

	def test_get_user_returns_user_for_valid_id(self):
		"""get_user() returns the LucosUser when a matching pk exists."""
		person = Person.objects.create()
		lucos_user = LucosUser.objects.create(agent=person)

		result = self.backend.get_user(lucos_user.pk)

		self.assertIsNotNone(result)
		self.assertEqual(result.pk, lucos_user.pk)

	def test_get_user_returns_none_for_unknown_id(self):
		"""get_user() returns None when no LucosUser exists with the given pk."""
		result = self.backend.get_user(99999)
		self.assertIsNone(result)
