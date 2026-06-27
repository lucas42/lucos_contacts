"""
JWKS/JWT verification for aithne sessions (ADR-0002).

contacts-specific differences from the eolas reference:
  - map_principal: sub → Person (by pk) → get_or_create(Django User) + scope-driven
    is_staff/is_superuser; User.first_name populated from Person.getName() for navbar.
  - Scopes: contacts:read (browse layer), contacts:admin (Django admin access).
  - Fails closed in production if no Person matches sub — contacts is the identity
    authority aithne calls, so a missing Person is a genuine config error.

Public API:
  verify_aithne_token(token_str)                      -> (principal_class, sub, scopes) or None
  map_principal(request, principal_class, sub, scopes) -> None
  aithne_login_redirect(request, next_path=None)       -> HttpResponseRedirect
  get_aithne_origin()                                  -> str
"""

import logging
import os
import re
import threading
from urllib.parse import urlencode

import jwt
from jwt import PyJWKClient, PyJWKClientError

logger = logging.getLogger(__name__)

# Import PyJWKClientNetworkError if available (PyJWT >= 2.4.0); fall back to
# the base class so the except clause still catches network failures.
try:
    from jwt import PyJWKClientNetworkError
except ImportError:
    PyJWKClientNetworkError = PyJWKClientError

_AITHNE_ORIGIN = os.environ.get("AITHNE_ORIGIN", "https://aithne.l42.eu")
# AITHNE_JWKS_URL overrides the JWKS fetch address (e.g. Docker bridge IP in dev).
# It must NOT influence the iss check or ?next= redirect — both derive from
# AITHNE_ORIGIN only.
_AITHNE_JWKS_URL = os.environ.get("AITHNE_JWKS_URL") or f"{_AITHNE_ORIGIN}/.well-known/jwks.json"
_AITHNE_ISSUER = _AITHNE_ORIGIN
_AITHNE_AUDIENCE = "l42.eu"


class _LKGJWKSClient:
    """PyJWKClient wrapper that serves last-known-good keys on network failure.

    Falls back to the last successfully fetched signing key when a network
    error occurs.  Cold-start (no cached key) fails closed — the token is
    rejected and the caller treats the request as unauthenticated.
    """

    def __init__(self, uri):
        self._client = PyJWKClient(uri, cache_keys=True, lifespan=300)
        self._last_good_key = None
        self._lock = threading.Lock()

    def get_signing_key_from_jwt(self, token):
        try:
            key = self._client.get_signing_key_from_jwt(token)
            with self._lock:
                self._last_good_key = key
            return key
        except PyJWKClientNetworkError as e:
            with self._lock:
                fallback = self._last_good_key
            safe_msg = re.sub(r'[\x00-\x1f\x7f]', '', str(e))
            if fallback is None:
                logger.warning("JWKS fetch failed at cold start (no cached key — failing closed): %s", safe_msg)
                raise
            logger.warning("JWKS fetch failed (using last-known-good): %s", safe_msg)
            return fallback
        # Any other PyJWKClientError (e.g. kid not found after refresh) propagates normally.


# Module-level client shared across all requests.
_jwks_client = _LKGJWKSClient(_AITHNE_JWKS_URL)


def _set_jwks_client(client):
    """Override the JWKS client. For testing only — do not call in production."""
    global _jwks_client
    _jwks_client = client


def get_aithne_origin():
    """Return AITHNE_ORIGIN, always fresh from the environment (testable)."""
    return os.environ.get("AITHNE_ORIGIN", "https://aithne.l42.eu")


def verify_aithne_token(token_str):
    """Verify an aithne-issued JWT.

    Returns a (principal_class, sub, scopes) tuple on success, or None on any
    failure (bad signature, expired, missing claims, etc.).

    - ES256 with algorithm pinning (never trust the header alg field)
    - iss == AITHNE_ORIGIN, aud contains l42.eu
    - exp/iat with 30-second clock-skew leeway; exp/iat/sub required
    """
    # Phase 1 — resolve signing key from JWKS.  Network/parse failures are
    # logged with specific messages by _LKGJWKSClient; we just surface them here.
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token_str)
    except PyJWKClientNetworkError:
        logger.warning("JWT rejected: JWKS unreachable and no cached key available")
        return None
    except PyJWKClientError as exc:
        logger.warning("JWT rejected: JWKS client error (%s: %s)", type(exc).__name__, exc)
        return None
    except jwt.DecodeError as exc:
        logger.warning("JWT rejected: malformed token (can't parse header) — %s", exc)
        return None

    # Phase 2 — decode and validate the JWT payload.
    try:
        payload = jwt.decode(
            token_str,
            signing_key.key,
            algorithms=["ES256"],
            issuer=_AITHNE_ISSUER,
            audience=_AITHNE_AUDIENCE,
            leeway=30,
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        logger.warning("JWT rejected: token has expired")
        return None
    except jwt.InvalidIssuerError:
        logger.warning("JWT rejected: wrong issuer (expected '%s')", _AITHNE_ISSUER)
        return None
    except jwt.InvalidAudienceError:
        logger.warning("JWT rejected: wrong audience (expected '%s')", _AITHNE_AUDIENCE)
        return None
    except jwt.MissingRequiredClaimError as exc:
        logger.warning("JWT rejected: missing required claim — %s", exc)
        return None
    except jwt.DecodeError as exc:
        logger.warning("JWT rejected: decode error — %s", exc)
        return None
    except jwt.InvalidTokenError as exc:
        logger.warning("JWT rejected: %s — %s", type(exc).__name__, exc)
        return None

    principal_class = payload.get("principal_class")
    if principal_class not in ("human", "agent"):
        logger.warning(
            "JWT rejected: unknown principal_class %r (expected 'human' or 'agent')",
            principal_class,
        )
        return None
    scopes = payload.get("scopes") or []
    sub = payload["sub"]
    logger.debug(
        "JWT verified: principal_class=%s sub=%.30s scopes=%s",
        principal_class, sub, scopes,
    )
    return (principal_class, sub, scopes)


def map_principal(request, principal_class, sub, scopes):
    """Map a verified JWT principal to a Django user and populate request.user.

    Authorization is scope-only (ADR-0002 §4/§6): is_staff and is_superuser
    are derived from scopes, never from principal_class.  principal_class is
    used only to identify the principal in log output.

    contacts-specific: sub is resolved to a Person (by pk), then a Django User
    is created/fetched for the session.  User.first_name is populated from
    Person.getName() so the navbar can display the human name rather than sub.

    In production, if no Person matches sub we log a warning and leave
    request.user as AnonymousUser — contacts is the identity authority and a
    missing Person is a genuine configuration error, not a recoverable state.
    In non-production, a Person is auto-created (matching old LucosAuthBackend
    behaviour for dev/test environments).
    """
    from django.contrib.auth.models import User
    from agents.models import Person

    has_admin = "contacts:admin" in scopes
    env = os.environ.get("ENVIRONMENT", "production")
    is_render_ui_read = (
        env == "development"
        and "render-ui" in scopes
        and request.method in ("GET", "HEAD")
    )

    # Resolve Person from sub.  contacts uses the Person pk (integer) as the
    # aithne principal sub.
    person = None
    try:
        person_pk = int(sub)
    except (ValueError, TypeError):
        logger.warning(
            "JWT sub %r is not a valid Person pk — treating as unauthenticated",
            sub[:30] if isinstance(sub, str) else sub,
        )
        return

    try:
        person = Person.objects.get(pk=person_pk)
    except Person.DoesNotExist:
        if env != "production":
            person, created = Person.objects.get_or_create(pk=person_pk)
            if created:
                logger.info("Auto-created Person pk=%s in non-production environment", person_pk)
        else:
            logger.warning(
                "No Person with pk=%s found in production — treating as unauthenticated",
                person_pk,
            )
            return

    # Get or create a Django User keyed on sub.  is_staff/is_superuser are set
    # from scopes in-memory only (not persisted) so they reflect the current
    # token's grants without touching the DB on every request.
    user, _ = User.objects.get_or_create(username=sub)
    user.is_staff = has_admin or is_render_ui_read
    user.is_superuser = has_admin
    # Populate display name from Person record so the navbar renders the
    # human's name (via get_short_name() → first_name) rather than the raw sub.
    user.first_name = person.getName()
    # Allow Django's auth decorators (e.g. @login_required) to accept this user
    # without a full authentication backend round-trip.
    user.backend = "django.contrib.auth.backends.ModelBackend"
    # Set .agent to the resolved Person so views that call request.user.agent
    # (e.g. agent(), agentindex()) work correctly — matching the .agent = None
    # convention on EnvVarUser and LucosUser.  In-memory only, no DB write.
    user.agent = person
    request.user = user
    logger.debug(
        "Mapped %s '%s' → User pk=%s (Person pk=%s, name=%r) staff=%s superuser=%s",
        principal_class, sub[:30], user.pk, person_pk, person.getName(),
        user.is_staff, user.is_superuser,
    )


def aithne_login_redirect(request, next_path=None):
    """Return a redirect to the aithne login page.

    next_path: local path to return to after login (default: request.path).
    A full URL is built from next_path so aithne knows which origin to
    redirect back to after authentication.
    """
    from django.shortcuts import redirect

    path = next_path if next_path is not None else request.path
    next_url = request.build_absolute_uri(path)
    aithne_origin = get_aithne_origin()
    login_url = f"{aithne_origin}/auth/login?{urlencode({'next': next_url})}"
    logger.debug("Redirecting to aithne login (next=%s)", next_url)
    return redirect(login_url)
