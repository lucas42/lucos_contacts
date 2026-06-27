import logging
from functools import wraps

from django.http import HttpResponse
from django.utils.html import escape

from lucosauth.envvars import getUserByKey

logger = logging.getLogger(__name__)


def api_auth(func):
	@wraps(func)
	def _decorator(request, *args, **kwargs):
		if 'HTTP_AUTHORIZATION' in request.META:
			authmeth, auth = request.META['HTTP_AUTHORIZATION'].split(' ', 1)
			if authmeth.lower() == 'bearer':
				user = getUserByKey(apikey=auth)
				if user:
					request.user = user
				else:
					return HttpResponse(status=403)
		return func(request, *args, **kwargs)
	return _decorator


def require_scope(scope):
	"""Decorator that enforces aithne JWT authentication and scope on a view.

	Three-branch pattern (ADR-0002 §4):
	  1. Required scope present → proceed.
	     (Scopes are only populated when the JWT verifies, so this implies
	     a valid token — no need to check is_authenticated separately.)
	  2. Scope absent + authenticated (valid JWT or machine @api_auth) → styled
	     403 naming only the missing scope (no scope enumeration).
	     Not a redirect — re-login yields the same token, which would loop.
	  3. Scope absent + not authenticated (no valid JWT) → redirect to
	     aithne login with the current page as ?next= (full absolute URL).

	When stacked with @api_auth, machine-authed requests (EnvVarUser with
	_is_api_user=True) are let through without scope checks — machine auth is
	handled entirely by @api_auth and does not use aithne scopes.

	request.aithne_scopes is populated by AithneAuthMiddleware.
	"""
	def decorator(f):
		@wraps(f)
		def _decorator(request, *args, **kwargs):
			# Machine auth (@api_auth) already handled — bypass aithne scope check.
			if getattr(request.user, '_is_api_user', False):
				return f(request, *args, **kwargs)

			scopes = getattr(request, 'aithne_scopes', [])

			# Branch 1: scope present → proceed
			if scope in scopes:
				return f(request, *args, **kwargs)

			# Branch 2: authenticated (valid JWT) but scope missing → 403
			if request.user.is_authenticated:
				logger.warning(
					"Access denied to %s: principal '%s' lacks required scope '%s'",
					request.path, getattr(request.user, 'username', str(request.user)), scope,
				)
				return HttpResponse(
					"<html><head><title>Access Denied</title>"
					"<meta charset=\"utf-8\"></head><body>"
					"<p>You don't have access to this page. "
					"Required scope: <code>" + escape(scope) + "</code></p>"
					"<nav><a href='/'>&#8592; Home</a></nav></body></html>",
					status=403,
					content_type="text/html; charset=utf-8",
				)

			# Branch 3: no valid token → redirect to aithne login
			from lucosauth.aithne import aithne_login_redirect
			logger.warning(
				"Unauthenticated request to %s — no valid aithne token, redirecting to login",
				request.path,
			)
			return aithne_login_redirect(request)

		return _decorator
	return decorator


def calendar_auth(func):
	@wraps(func)
	def _decorator(request, *args, **kwargs):
		if 'key' in request.GET:
			user = getUserByKey(apikey=request.GET['key'])
			if user:
				request.user = user
			else:
				return HttpResponse(status=403)
		return func(request, *args, **kwargs)
	return _decorator