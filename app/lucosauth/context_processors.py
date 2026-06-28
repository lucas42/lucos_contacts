"""
Template context processors for lucosauth.
"""

import os


def aithne_origin(request):
    """Inject AITHNE_ORIGIN into all template contexts.

    Used by templates/navbar.html to set the aithne-origin attribute on
    <lucos-navbar>, enabling the session keepalive to call the right aithne
    instance (ADR-0003).
    """
    return {
        "AITHNE_ORIGIN": os.environ.get("AITHNE_ORIGIN", "https://aithne.l42.eu"),
    }
