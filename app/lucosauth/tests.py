import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import AnonymousUser, User
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, Client, override_settings

from lucosauth.decorators import api_auth, require_scope
from lucosauth.middleware import AithneAuthMiddleware
from lucosauth.models import LucosAuthBackend, LucosUser
from lucosauth.views import loginview
from agents.models import Person


AUTH_HEADER = {'HTTP_AUTHORIZATION': 'bearer 1234'}


def json_urlopen_response(data):
	"""Return a BytesIO that json.load() can read, simulating a urllib urlopen response."""
	return io.BytesIO(json.dumps(data).encode())


# ---------------------------------------------------------------------------
# @api_auth — regression coverage
# ---------------------------------------------------------------------------

class ApiAuthDecoratorTest(TestCase):
	"""Tests for the api_auth decorator behaviour.

	Uses /people/all (which is now decorated with @api_auth + @require_scope)
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

	def test_no_auth_header_redirects_to_aithne_login(self):
		"""No auth header falls through to @require_scope which redirects to aithne."""
		response = self.client.get('/people/all', HTTP_ACCEPT='application/json')
		self.assertEqual(response.status_code, 302)
		# Must redirect to aithne login, not the old /accounts/login
		self.assertIn('/auth/login', response['Location'])

	def test_valid_key_allows_access(self):
		"""A valid API key grants access to a protected endpoint."""
		response = self.client.get(
			'/people/all',
			HTTP_ACCEPT='application/json',
			**AUTH_HEADER,
		)
		self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# LoginView — new aithne-redirect behaviour
# ---------------------------------------------------------------------------

class LoginViewAithneRedirectTest(SimpleTestCase):
	"""The login view is now a plain redirect to aithne (no token handling)."""

	def setUp(self):
		self.factory = RequestFactory()

	def _call(self, url, aithne_origin='http://aithne.test'):
		request = self.factory.get(url)
		with patch.dict('os.environ', {'AITHNE_ORIGIN': aithne_origin}):
			return loginview(request)

	def test_no_next_redirects_to_aithne_login(self):
		response = self._call('/accounts/login')
		self.assertEqual(response.status_code, 302)
		self.assertIn('/auth/login', response['Location'])

	def test_same_origin_next_is_preserved(self):
		response = self._call('/accounts/login?next=/some/page/')
		self.assertEqual(response.status_code, 302)
		location = response['Location']
		self.assertIn('next=', location)

	def test_external_next_is_replaced_with_root(self):
		response = self._call('/accounts/login?next=https://evil.example.com/')
		self.assertEqual(response.status_code, 302)
		location = response['Location']
		self.assertNotIn('evil.example.com', location)

	def test_redirect_uses_aithne_origin(self):
		response = self._call('/accounts/login', aithne_origin='http://aithne.test')
		self.assertTrue(response['Location'].startswith('http://aithne.test/auth/login'))

	def test_no_longer_handles_token_param(self):
		"""The old ?token= flow is gone — redirect must not echo the raw token."""
		request = self.factory.get('/accounts/login?token=sometoken')
		with patch.dict('os.environ', {'AITHNE_ORIGIN': 'http://aithne.test'}):
			response = loginview(request)
		self.assertNotIn('token=sometoken', response['Location'])


# ---------------------------------------------------------------------------
# AithneAuthMiddleware
# ---------------------------------------------------------------------------

class AithneMiddlewareTest(SimpleTestCase):
	"""AithneAuthMiddleware is populate-only — never blocks."""

	def setUp(self):
		self.factory = RequestFactory()
		self.get_response = MagicMock(return_value=HttpResponse(status=200))

	def _get_middleware(self):
		return AithneAuthMiddleware(self.get_response)

	def _make_request(self, cookie=None, auth_header=None, path='/'):
		request = self.factory.get(path)
		request.user = AnonymousUser()
		request.aithne_scopes = []
		if cookie:
			request.COOKIES['aithne_session'] = cookie
		if auth_header:
			request.META['HTTP_AUTHORIZATION'] = auth_header
		return request

	def test_no_token_leaves_anonymous_user(self):
		mw = self._get_middleware()
		request = self._make_request()
		with patch('lucosauth.middleware.verify_aithne_token', return_value=None):
			mw(request)
		self.assertIsInstance(request.user, AnonymousUser)

	def test_no_token_still_calls_view(self):
		"""Middleware never blocks — it always calls get_response."""
		mw = self._get_middleware()
		request = self._make_request()
		with patch('lucosauth.middleware.verify_aithne_token', return_value=None):
			mw(request)
		self.get_response.assert_called_once()

	def test_valid_cookie_token_calls_verify_and_map(self):
		mw = self._get_middleware()
		request = self._make_request(cookie='valid.jwt.token')
		with patch('lucosauth.middleware.verify_aithne_token',
				   return_value=('human', '42', ['contacts:read'])) as mock_verify, \
			 patch('lucosauth.middleware.map_principal') as mock_map:
			mw(request)
		mock_verify.assert_called_once_with('valid.jwt.token')
		mock_map.assert_called_once_with(request, 'human', '42', ['contacts:read'])

	def test_valid_bearer_token_calls_verify_and_map(self):
		mw = self._get_middleware()
		request = self._make_request(auth_header='Bearer valid.jwt.token')
		with patch('lucosauth.middleware.verify_aithne_token',
				   return_value=('agent', 'lucos-ux', ['render-ui'])) as mock_verify, \
			 patch('lucosauth.middleware.map_principal') as mock_map:
			mw(request)
		mock_verify.assert_called_once_with('valid.jwt.token')

	def test_cookie_takes_priority_over_bearer(self):
		mw = self._get_middleware()
		request = self._make_request(
			cookie='cookie.jwt.token',
			auth_header='Bearer bearer.jwt.token',
		)
		with patch('lucosauth.middleware.verify_aithne_token',
				   return_value=None) as mock_verify, \
			 patch('lucosauth.middleware.map_principal'):
			mw(request)
		mock_verify.assert_called_once_with('cookie.jwt.token')

	def test_invalid_token_leaves_anonymous(self):
		mw = self._get_middleware()
		request = self._make_request(cookie='bad.jwt')
		with patch('lucosauth.middleware.verify_aithne_token', return_value=None):
			mw(request)
		self.assertIsInstance(request.user, AnonymousUser)

	def test_scopes_populated_on_request_on_success(self):
		mw = self._get_middleware()
		request = self._make_request(cookie='valid.jwt.token')

		mock_user = MagicMock()
		mock_user.is_authenticated = True

		def fake_map(req, pc, sub, scopes):
			req.user = mock_user

		with patch('lucosauth.middleware.verify_aithne_token',
				   return_value=('human', '42', ['contacts:read'])), \
			 patch('lucosauth.middleware.map_principal', side_effect=fake_map):
			mw(request)
		self.assertEqual(request.aithne_scopes, ['contacts:read'])


# ---------------------------------------------------------------------------
# @require_scope — three-branch enforcement
# ---------------------------------------------------------------------------

class RequireScopeDecoratorTest(SimpleTestCase):
	"""@require_scope enforces the three-branch pattern (ADR-0002 §4)."""

	def setUp(self):
		self.factory = RequestFactory()

	def _make_protected_view(self, scope='contacts:read'):
		@require_scope(scope)
		def view(request):
			return HttpResponse(status=200)
		return view

	def _make_auth_request(self, scopes=None, authenticated=True, path='/people/all'):
		request = self.factory.get(path)
		if authenticated:
			user = MagicMock(spec=User)
			user.is_authenticated = True
			user.username = 'testuser'
			user._is_api_user = False  # prevent MagicMock(spec=) auto-attr from being truthy
			request.user = user
		else:
			request.user = AnonymousUser()
		request.aithne_scopes = scopes or []
		return request

	def test_valid_token_with_required_scope_proceeds(self):
		"""Branch 1: valid token + scope → 200."""
		view = self._make_protected_view('contacts:read')
		request = self._make_auth_request(scopes=['contacts:read'])
		response = view(request)
		self.assertEqual(response.status_code, 200)

	def test_valid_token_missing_scope_returns_403(self):
		"""Branch 2: valid token, scope absent → styled 403."""
		view = self._make_protected_view('contacts:read')
		request = self._make_auth_request(scopes=['some:other'])
		response = view(request)
		self.assertEqual(response.status_code, 403)

	def test_403_body_names_missing_scope_only(self):
		"""The 403 body must name the required scope and NOT enumerate granted scopes."""
		view = self._make_protected_view('contacts:admin')
		request = self._make_auth_request(scopes=['contacts:read'])
		response = view(request)
		self.assertEqual(response.status_code, 403)
		self.assertIn(b'contacts:admin', response.content)
		# Must NOT enumerate the granted scopes
		self.assertNotIn(b'contacts:read', response.content)

	def test_no_token_redirects_to_aithne_login(self):
		"""Branch 3: no valid token → redirect to aithne login."""
		view = self._make_protected_view('contacts:read')
		request = self._make_auth_request(authenticated=False)
		with patch.dict('os.environ', {'AITHNE_ORIGIN': 'http://aithne.test'}):
			response = view(request)
		self.assertEqual(response.status_code, 302)
		self.assertIn('http://aithne.test/auth/login', response['Location'])

	def test_redirect_includes_absolute_next_param(self):
		"""Login redirect includes the current URL as full absolute ?next= (not bare path)."""
		view = self._make_protected_view('contacts:read')
		request = self._make_auth_request(authenticated=False, path='/people/starred')
		with patch.dict('os.environ', {'AITHNE_ORIGIN': 'http://aithne.test'}):
			response = view(request)
		location = response['Location']
		self.assertIn('next=', location)
		# next= must be a full URL (testserver is the RequestFactory host)
		self.assertIn('testserver', location)

	def test_machine_auth_bypasses_scope_check(self):
		"""EnvVarUser (_is_api_user=True) passes @require_scope without aithne scopes."""
		from lucosauth.envvars import EnvVarUser
		view = self._make_protected_view('contacts:read')
		request = self.factory.get('/people/all')
		request.user = EnvVarUser(system='test:test', apikey='testkey1234')
		request.aithne_scopes = []
		response = view(request)
		self.assertEqual(response.status_code, 200)

	def test_authenticated_wrong_scope_not_redirected(self):
		"""Branch 2 (403) — not branch 3 (redirect) — when authenticated but missing scope."""
		view = self._make_protected_view('contacts:admin')
		request = self._make_auth_request(authenticated=True, scopes=['contacts:read'])
		response = view(request)
		self.assertEqual(response.status_code, 403)


# ---------------------------------------------------------------------------
# verify_aithne_token — principal_class allowlist
# ---------------------------------------------------------------------------

class VerifyAithneTokenPrincipalClassTest(SimpleTestCase):
	"""verify_aithne_token must reject tokens with an unknown principal_class."""

	def _make_mock_jwks_client(self):
		mock = MagicMock()
		mock.get_signing_key_from_jwt.return_value = MagicMock()
		return mock

	@patch('lucosauth.aithne._jwks_client')
	@patch('jwt.decode')
	def test_unknown_principal_class_returns_none(self, mock_decode, mock_jwks_client):
		"""A token whose principal_class is not 'human' or 'agent' is rejected."""
		mock_decode.return_value = {
			'principal_class': 'alien',
			'sub': '42',
			'scopes': ['contacts:read'],
		}
		from lucosauth.aithne import verify_aithne_token
		result = verify_aithne_token('some.jwt.token')
		self.assertIsNone(result)

	@patch('lucosauth.aithne._jwks_client')
	@patch('jwt.decode')
	def test_none_principal_class_returns_none(self, mock_decode, mock_jwks_client):
		"""A token with no principal_class claim is rejected."""
		mock_decode.return_value = {
			'sub': '42',
			'scopes': ['contacts:read'],
		}
		from lucosauth.aithne import verify_aithne_token
		result = verify_aithne_token('some.jwt.token')
		self.assertIsNone(result)

	@patch('lucosauth.aithne._jwks_client')
	@patch('jwt.decode')
	def test_human_principal_class_is_accepted(self, mock_decode, mock_jwks_client):
		"""A token with principal_class='human' is accepted and returned."""
		mock_decode.return_value = {
			'principal_class': 'human',
			'sub': '42',
			'scopes': ['contacts:read'],
		}
		from lucosauth.aithne import verify_aithne_token
		result = verify_aithne_token('some.jwt.token')
		self.assertIsNotNone(result)
		self.assertEqual(result[0], 'human')

	@patch('lucosauth.aithne._jwks_client')
	@patch('jwt.decode')
	def test_agent_principal_class_is_accepted(self, mock_decode, mock_jwks_client):
		"""A token with principal_class='agent' is accepted and returned."""
		mock_decode.return_value = {
			'principal_class': 'agent',
			'sub': 'lucos-ux',
			'scopes': ['render-ui'],
		}
		from lucosauth.aithne import verify_aithne_token
		result = verify_aithne_token('some.jwt.token')
		self.assertIsNotNone(result)
		self.assertEqual(result[0], 'agent')


# ---------------------------------------------------------------------------
# map_principal — .agent attribute
# ---------------------------------------------------------------------------

class MapPrincipalAgentTest(TestCase):
	"""map_principal must set request.user.agent to the resolved Person."""

	def setUp(self):
		self.factory = RequestFactory()

	@patch.dict('os.environ', {'ENVIRONMENT': 'test'})
	def test_user_agent_set_to_person(self):
		"""After map_principal, request.user.agent == the resolved Person."""
		person = Person.objects.create()
		request = self.factory.get('/people/all')
		request.user = AnonymousUser()

		from lucosauth.aithne import map_principal
		map_principal(request, 'human', str(person.pk), ['contacts:read'])

		self.assertIsNotNone(request.user)
		self.assertTrue(request.user.is_authenticated)
		self.assertEqual(request.user.agent, person)

	@patch.dict('os.environ', {'ENVIRONMENT': 'test'})
	def test_user_agent_is_none_for_unknown_sub(self):
		"""map_principal with a non-integer sub leaves request.user unchanged."""
		request = self.factory.get('/people/all')
		original_user = AnonymousUser()
		request.user = original_user

		from lucosauth.aithne import map_principal
		map_principal(request, 'human', 'not-an-int', ['contacts:read'])

		# Should not have replaced the user
		self.assertIs(request.user, original_user)


# ---------------------------------------------------------------------------
# LucosAuthBackend — regression coverage (old session-auth backend)
# ---------------------------------------------------------------------------

class LucosAuthBackendTest(TestCase):
	"""Tests for LucosAuthBackend — the legacy session-cookie auth flow.

	authenticate() calls the auth service with the token from the session
	cookie, then finds or creates the matching Person and LucosUser.
	Retained as regression coverage; the backend is no longer called by
	the loginview but remains in AUTHENTICATION_BACKENDS for compatibility.
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
