import logging

from django.http import HttpResponse
from django.utils.http import url_has_allowed_host_and_scheme

from .aithne import aithne_login_redirect

logger = logging.getLogger(__name__)


def loginview(request):
	"""Redirect to aithne login, or 403 if already authenticated (ADR-0002 §5).

	The aithne_session cookie is set domain-wide by aithne after authentication;
	AithneAuthMiddleware picks it up automatically on return — no ?token= handling
	or login() call needed.

	If the user is already authenticated (valid aithne session) but was sent here
	because they lack a required permission (scope or is_staff), redirecting to
	aithne login is unhelpful — they would get the same token back.  Return 403
	so it's clear the issue is authorisation, not authentication.

	?next= from the incoming query string is validated as an internal path, then
	forwarded as a full URL so aithne knows which origin to redirect back to.
	"""
	if getattr(request, 'user', None) is not None and request.user.is_authenticated:
		return HttpResponse(
			"<html><head><title>Access Denied</title>"
			"<meta charset=\"utf-8\"></head><body>"
			"<p>You don't have permission to access this page.</p>"
			"<nav><a href='/'>&#8592; Home</a></nav></body></html>",
			status=403,
			content_type="text/html; charset=utf-8",
		)
	next_path = request.GET.get("next", "/")
	if not url_has_allowed_host_and_scheme(url=next_path, allowed_hosts={request.get_host()}):
		logger.debug("loginview: rejecting external ?next=%s, falling back to /", next_path)
		next_path = "/"
	return aithne_login_redirect(request, next_path)   
