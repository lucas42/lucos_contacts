from unittest.mock import MagicMock, patch

from django.contrib.auth.models import AnonymousUser, User
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, Client, override_settings

from lucosauth.decorators import api_auth, require_scope
from lucosauth.middleware import AithneAuthMiddleware
from lucosauth.views import loginview
from agents.models import Person


AUTH_HEADER = {'HTTP_AUTHORIZATION': 'bearer 1234'}


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
# CryptographyAvailableTest — smoke tests to catch missing-cryptography failure
# ---------------------------------------------------------------------------

class CryptographyAvailableTest(SimpleTestCase):
	"""Verify the cryptography package and PyJWT ES256 support are available.

	These smoke tests catch a class of lockfile error where cffi or cryptography
	is missing from the installed packages, causing MissingCryptographyError at
	runtime under PyJWT 2.x.  They run before any token is verified in CI so
	the failure message is clear rather than buried in middleware exceptions.
	"""

	def test_cryptography_module_importable(self):
		"""The cryptography package is present and importable."""
		import cryptography
		self.assertIsNotNone(cryptography)

	def test_es256_key_generation(self):
		"""ES256 (ECDSA P-256) key generation works — requires cryptography package."""
		from cryptography.hazmat.primitives.asymmetric import ec
		key = ec.generate_private_key(ec.SECP256R1())
		self.assertIsNotNone(key)

	def test_pyjwt_es256_encode_decode(self):
		"""PyJWT can encode and decode a JWT with ES256 algorithm."""
		from cryptography.hazmat.primitives.asymmetric import ec
		import jwt

		private_key = ec.generate_private_key(ec.SECP256R1())
		public_key = private_key.public_key()
		token = jwt.encode({'sub': 'smoke-test', 'iss': 'test'}, private_key, algorithm='ES256')
		payload = jwt.decode(token, public_key, algorithms=['ES256'], options={'verify_aud': False})
		self.assertEqual(payload['sub'], 'smoke-test')


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

	def test_authenticated_user_gets_403_not_redirect(self):
		"""Authenticated user hitting /accounts/login returns 403, not aithne redirect.

		An authenticated user sent to /accounts/login lacks a required scope or
		is_staff flag — not an aithne session.  Redirecting to aithne login is
		unhelpful (they'd get the same token back); 403 makes the problem clear.
		"""
		from unittest.mock import MagicMock
		request = self.factory.get('/accounts/login?next=/admin/')
		user = MagicMock()
		user.is_authenticated = True
		request.user = user
		with patch.dict('os.environ', {'AITHNE_ORIGIN': 'http://aithne.test'}):
			response = loginview(request)
		self.assertEqual(response.status_code, 403)
		# Must NOT redirect to aithne login
		self.assertFalse(hasattr(response, 'url') and 'aithne.test' in response.get('Location', ''))


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
				   return_value=('42', ['contacts:read'])) as mock_verify, \
			 patch('lucosauth.middleware.map_principal') as mock_map:
			mw(request)
		mock_verify.assert_called_once_with('valid.jwt.token')
		mock_map.assert_called_once_with(request, '42', ['contacts:read'])

	def test_valid_bearer_token_calls_verify_and_map(self):
		mw = self._get_middleware()
		request = self._make_request(auth_header='Bearer valid.jwt.token')
		with patch('lucosauth.middleware.verify_aithne_token',
				   return_value=('lucos-ux', ['render-ui'])) as mock_verify, \
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

		def fake_map(req, sub, scopes):
			req.user = mock_user

		with patch('lucosauth.middleware.verify_aithne_token',
				   return_value=('42', ['contacts:read'])), \
			 patch('lucosauth.middleware.map_principal', side_effect=fake_map):
			mw(request)
		self.assertEqual(request.aithne_scopes, ['contacts:read'])

	def test_plain_api_key_in_bearer_not_verified(self):
		"""Bearer tokens that lack JWT structure (three segments) are ignored.

		Plain lucos_creds API keys look like 'somekey=1234' — not JWTs.  The
		middleware must not pass them to verify_aithne_token (which would log
		a noisy WARNING on every machine-authed request).
		"""
		mw = self._get_middleware()
		request = self._make_request(auth_header='Bearer somekey=1234')
		with patch('lucosauth.middleware.verify_aithne_token') as mock_verify:
			mw(request)
		mock_verify.assert_not_called()

	def test_jwt_shaped_bearer_is_verified(self):
		"""Bearer tokens with JWT structure (three base64url segments) ARE verified."""
		mw = self._get_middleware()
		request = self._make_request(auth_header='Bearer aaa.bbb.ccc')
		with patch('lucosauth.middleware.verify_aithne_token',
				   return_value=None) as mock_verify, \
			 patch('lucosauth.middleware.map_principal'):
			mw(request)
		mock_verify.assert_called_once_with('aaa.bbb.ccc')


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

	def test_machine_user_with_scope_passes(self):
		"""EnvVarUser with the required scope in .scopes passes @require_scope."""
		from lucosauth.envvars import EnvVarUser
		view = self._make_protected_view('contacts:read')
		request = self.factory.get('/people/all')
		request.user = EnvVarUser(system='importer', apikey='testkey1234', scopes=['contacts:read'])
		request.aithne_scopes = []
		response = view(request)
		self.assertEqual(response.status_code, 200)

	def test_machine_user_without_scope_returns_403(self):
		"""EnvVarUser with no matching scope in .scopes is rejected with 403."""
		from lucosauth.envvars import EnvVarUser
		view = self._make_protected_view('contacts:write')
		request = self.factory.get('/people/all')
		request.user = EnvVarUser(system='readonly_caller', apikey='testkey5678')
		request.aithne_scopes = []
		response = view(request)
		self.assertEqual(response.status_code, 403)

	def test_machine_user_without_scope_ignores_aithne_scopes(self):
		"""Scopeless EnvVarUser is not elevated by a JWT cookie on the same request.

		AithneAuthMiddleware populates request.aithne_scopes before @api_auth
		overrides request.user, so a machine key without |scope suffix that also
		carries an aithne_session cookie must NOT inherit the JWT's scopes.
		"""
		from lucosauth.envvars import EnvVarUser
		view = self._make_protected_view('contacts:read')
		request = self.factory.get('/people/all')
		request.user = EnvVarUser(system='scopeless_caller', apikey='nokey')
		request.aithne_scopes = ['contacts:read']  # JWT cookie bleed-through
		response = view(request)
		self.assertEqual(response.status_code, 403)

	def test_authenticated_wrong_scope_not_redirected(self):
		"""Branch 2 (403) — not branch 3 (redirect) — when authenticated but missing scope."""
		view = self._make_protected_view('contacts:admin')
		request = self._make_auth_request(authenticated=True, scopes=['contacts:read'])
		response = view(request)
		self.assertEqual(response.status_code, 403)


# ---------------------------------------------------------------------------
# verify_aithne_token — returns (sub, scopes)
# ---------------------------------------------------------------------------

class VerifyAithneTokenTest(SimpleTestCase):
	"""verify_aithne_token returns (sub, scopes) on success, None on failure.

	Scope is the gate (ADR-0002 §4/§6) — principal_class is logged but not
	returned.  Authorization never branches on who the principal is.
	"""

	@patch('lucosauth.aithne._jwks_client')
	@patch('jwt.decode')
	def test_valid_token_returns_sub_and_scopes(self, mock_decode, mock_jwks_client):
		"""A valid token returns a (sub, scopes) 2-tuple."""
		mock_decode.return_value = {
			'principal_class': 'human',
			'sub': '42',
			'scopes': ['contacts:read'],
		}
		from lucosauth.aithne import verify_aithne_token
		result = verify_aithne_token('some.jwt.token')
		self.assertIsNotNone(result)
		sub, scopes = result
		self.assertEqual(sub, '42')
		self.assertEqual(scopes, ['contacts:read'])

	@patch('lucosauth.aithne._jwks_client')
	@patch('jwt.decode')
	def test_agent_token_returns_sub_and_scopes(self, mock_decode, mock_jwks_client):
		"""An agent token returns its sub and scopes — principal_class not in result."""
		mock_decode.return_value = {
			'principal_class': 'agent',
			'sub': 'lucos-ux',
			'scopes': ['render-ui'],
		}
		from lucosauth.aithne import verify_aithne_token
		result = verify_aithne_token('some.jwt.token')
		self.assertIsNotNone(result)
		sub, scopes = result
		self.assertEqual(sub, 'lucos-ux')
		self.assertEqual(scopes, ['render-ui'])

	@patch('lucosauth.aithne._jwks_client')
	@patch('jwt.decode')
	def test_token_without_principal_class_is_accepted(self, mock_decode, mock_jwks_client):
		"""A token without a principal_class claim is accepted — scope is the gate."""
		mock_decode.return_value = {
			'sub': '42',
			'scopes': ['contacts:read'],
		}
		from lucosauth.aithne import verify_aithne_token
		result = verify_aithne_token('some.jwt.token')
		self.assertIsNotNone(result)
		sub, scopes = result
		self.assertEqual(sub, '42')


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
		map_principal(request, str(person.pk), ['contacts:read'])

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
		map_principal(request, 'not-an-int', ['contacts:read'])

		# Should not have replaced the user
		self.assertIs(request.user, original_user)


# ---------------------------------------------------------------------------
# _LKGJWKSClient — reachability tracking (lucas42/lucos_contacts#772)
# ---------------------------------------------------------------------------

class LKGJWKSClientReachabilityTest(SimpleTestCase):
	"""_LKGJWKSClient tracks whether the most recent fetch attempt hit a
	network error, independent of whether a last-known-good key let
	verification succeed anyway.
	"""

	def setUp(self):
		from lucosauth.aithne import _LKGJWKSClient, PyJWKClientNetworkError
		self.error_cls = PyJWKClientNetworkError
		self.client = _LKGJWKSClient.__new__(_LKGJWKSClient)
		self.client._client = MagicMock()
		self.client._last_good_key = None
		self.client._unreachable = False
		import threading
		self.client._lock = threading.Lock()

	def test_starts_reachable(self):
		self.assertFalse(self.client.is_unreachable())

	def test_cold_start_network_error_marks_unreachable(self):
		"""No cached key + network error: fails closed AND marks unreachable."""
		self.client._client.get_signing_key_from_jwt.side_effect = self.error_cls("boom")
		with self.assertRaises(self.error_cls):
			self.client.get_signing_key_from_jwt('token')
		self.assertTrue(self.client.is_unreachable())

	def test_network_error_with_cached_key_still_marks_unreachable(self):
		"""Even when a last-known-good key masks the failure from the caller,
		the reachability signal must still flip — aithne's login page is down
		regardless of whether an existing session can still verify."""
		cached_key = MagicMock()
		self.client._last_good_key = cached_key
		self.client._client.get_signing_key_from_jwt.side_effect = self.error_cls("boom")
		result = self.client.get_signing_key_from_jwt('token')
		self.assertEqual(result, cached_key)
		self.assertTrue(self.client.is_unreachable())

	def test_successful_fetch_clears_unreachable(self):
		"""A successful fetch (fresh or from the underlying client's own cache)
		self-heals the reachability signal — no separate recovery step needed."""
		self.client._unreachable = True
		self.client._client.get_signing_key_from_jwt.return_value = 'a-key'
		result = self.client.get_signing_key_from_jwt('token')
		self.assertEqual(result, 'a-key')
		self.assertFalse(self.client.is_unreachable())


class IsAithneReachableTest(SimpleTestCase):
	"""is_aithne_reachable() reflects the shared JWKS client's state."""

	def test_reflects_jwks_client_unreachable(self):
		import lucosauth.aithne as aithne_mod
		mock_client = MagicMock()
		mock_client.is_unreachable.return_value = True
		with patch.object(aithne_mod, '_jwks_client', mock_client):
			self.assertFalse(aithne_mod.is_aithne_reachable())

	def test_reflects_jwks_client_reachable(self):
		import lucosauth.aithne as aithne_mod
		mock_client = MagicMock()
		mock_client.is_unreachable.return_value = False
		with patch.object(aithne_mod, '_jwks_client', mock_client):
			self.assertTrue(aithne_mod.is_aithne_reachable())


# ---------------------------------------------------------------------------
# require_scope branch 3 — local page vs redirect when aithne is unreachable
# ---------------------------------------------------------------------------

class RequireScopeAithneUnavailableTest(SimpleTestCase):
	"""Branch 3 renders a local page instead of redirecting when aithne is
	known to be unreachable (lucas42/lucos_contacts#772)."""

	def setUp(self):
		self.factory = RequestFactory()

	def _make_protected_view(self, scope='contacts:read'):
		@require_scope(scope)
		def view(request):
			return HttpResponse(status=200)
		return view

	def _make_unauth_request(self, path='/people/all'):
		request = self.factory.get(path)
		request.user = AnonymousUser()
		request.aithne_scopes = []
		return request

	def test_renders_local_page_when_unreachable(self):
		view = self._make_protected_view()
		request = self._make_unauth_request()
		with patch('lucosauth.aithne.is_aithne_reachable', return_value=False):
			response = view(request)
		self.assertEqual(response.status_code, 503)
		self.assertIn(b'temporarily unavailable', response.content.lower())

	def test_does_not_redirect_when_unreachable(self):
		view = self._make_protected_view()
		request = self._make_unauth_request()
		with patch('lucosauth.aithne.is_aithne_reachable', return_value=False):
			response = view(request)
		self.assertNotEqual(response.status_code, 302)

	def test_still_redirects_when_reachable(self):
		"""Existing behaviour is preserved when aithne is up."""
		view = self._make_protected_view()
		request = self._make_unauth_request()
		with patch('lucosauth.aithne.is_aithne_reachable', return_value=True), \
			 patch.dict('os.environ', {'AITHNE_ORIGIN': 'http://aithne.test'}):
			response = view(request)
		self.assertEqual(response.status_code, 302)
		self.assertIn('/auth/login', response['Location'])
