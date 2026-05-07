from django.test import TestCase, Client


AUTH_HEADER = {'HTTP_AUTHORIZATION': 'key 1234'}


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
			HTTP_AUTHORIZATION='key wrongkey',
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
