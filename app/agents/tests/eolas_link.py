# -*- coding: utf-8 -*-
"""
Tests for the eolas_uri cross-system link on Person.

Covers:
- RDF emission: owl:sameAs and preferredIdentifier present when eolas_uri set.
- RDF emission: neither triple emitted when eolas_uri is null.
- Loganne events: contactLinked (initial link, relink), contactUnlinked,
  contactUpdated alongside, and no event when eolas_uri is unchanged.
"""

import rdflib
from unittest.mock import call, patch

from django.test import TestCase
from django.urls import reverse

from agents.models import Person, PersonName
from agents.tests.admin import AdminJourneyTestCase, make_person
from agents.utils_rdf import agent_to_rdf, EOLAS_NS


EOLAS_URI_A = "https://eolas.l42.eu/metadata/person/42/"
EOLAS_URI_B = "https://eolas.l42.eu/metadata/person/99/"


# ── RDF Tests ─────────────────────────────────────────────────────────────────


class RdfEolasUriTest(TestCase):
    """Unit tests for owl:sameAs and preferredIdentifier emission in RDF."""

    def _make_person_with_eolas_uri(self, eolas_uri):
        person = Person.objects.create(eolas_uri=eolas_uri)
        PersonName.objects.create(agent=person, name="Alice")
        return person

    def test_eolas_uri_set_emits_same_as(self):
        """A contact with eolas_uri emits owl:sameAs pointing to that URI."""
        person = self._make_person_with_eolas_uri(EOLAS_URI_A)
        g = agent_to_rdf(person)
        subject = list(g.subjects(rdflib.RDF.type, rdflib.FOAF.Person))[0]
        self.assertIn(
            (subject, rdflib.OWL.sameAs, rdflib.URIRef(EOLAS_URI_A)),
            g,
            "owl:sameAs triple must be present when eolas_uri is set",
        )

    def test_eolas_uri_set_emits_preferred_identifier(self):
        """A contact with eolas_uri emits preferredIdentifier pointing to that URI."""
        person = self._make_person_with_eolas_uri(EOLAS_URI_A)
        g = agent_to_rdf(person)
        subject = list(g.subjects(rdflib.RDF.type, rdflib.FOAF.Person))[0]
        self.assertIn(
            (subject, EOLAS_NS.preferredIdentifier, rdflib.URIRef(EOLAS_URI_A)),
            g,
            "preferredIdentifier triple must be present when eolas_uri is set",
        )

    def test_eolas_uri_preferred_identifier_uses_full_uri(self):
        """preferredIdentifier value is the full URI, not a relative path."""
        person = self._make_person_with_eolas_uri(EOLAS_URI_A)
        g = agent_to_rdf(person)
        subject = list(g.subjects(rdflib.RDF.type, rdflib.FOAF.Person))[0]
        pred_values = list(g.objects(subject, EOLAS_NS.preferredIdentifier))
        self.assertEqual(len(pred_values), 1)
        # The value should be the eolas URI, not the predicate URI
        self.assertEqual(str(pred_values[0]), EOLAS_URI_A)

    def test_no_eolas_uri_no_same_as(self):
        """A contact without eolas_uri must NOT emit owl:sameAs."""
        person = Person.objects.create()
        PersonName.objects.create(agent=person, name="Bob")
        g = agent_to_rdf(person)
        subject = list(g.subjects(rdflib.RDF.type, rdflib.FOAF.Person))[0]
        same_as_objects = list(g.objects(subject, rdflib.OWL.sameAs))
        self.assertEqual(
            same_as_objects, [],
            "owl:sameAs must not appear when eolas_uri is null",
        )

    def test_no_eolas_uri_no_preferred_identifier(self):
        """A contact without eolas_uri must NOT emit preferredIdentifier."""
        person = Person.objects.create()
        PersonName.objects.create(agent=person, name="Bob")
        g = agent_to_rdf(person)
        subject = list(g.subjects(rdflib.RDF.type, rdflib.FOAF.Person))[0]
        pref_id_objects = list(g.objects(subject, EOLAS_NS.preferredIdentifier))
        self.assertEqual(
            pref_id_objects, [],
            "preferredIdentifier must not appear when eolas_uri is null",
        )


# ── Loganne Event Tests ────────────────────────────────────────────────────────


class EolasLinkLoganneTest(AdminJourneyTestCase):
    """
    Tests for contactLinked / contactUnlinked / contactUpdated Loganne events
    fired via the admin save flow when eolas_uri changes.

    Uses AdminJourneyTestCase so that the test client is authenticated against
    the Django admin — which is the only editing path for eolas_uri.
    """

    def _change_url(self, person):
        return reverse('admin:agents_person_change', args=[person.pk])

    def _build_post_data(self, person, extra=None):
        """
        Build the minimal POST dict for a Person change-form submission.

        GETs the change form to extract inline management-form data, then
        injects `extra` overrides on top.
        """
        get_response = self.client.get(self._change_url(person))
        self.assertEqual(get_response.status_code, 200)
        data = self._post_data_from_response(get_response)
        if extra:
            data.update(extra)
        return data

    def _post_change(self, person, extra=None):
        """POST a Person change form and return the response."""
        data = self._build_post_data(person, extra)
        return self.client.post(self._change_url(person), data)

    # ── Helpers to extract Loganne calls by type ─────────────────────────────

    def _calls_of_type(self, mock_loganne, event_type):
        return [
            c for c in mock_loganne.call_args_list
            if c.args and c.args[0].get('type') == event_type
        ]

    # ── Test 1: initial link (null → URI) ────────────────────────────────────

    def test_initial_link_fires_contact_linked(self):
        """
        Setting eolas_uri from null fires contactLinked with previousEolasUri=null.
        """
        person = make_person('Alice')
        with patch('agents.loganne.loganneRequest') as mock_loganne:
            response = self._post_change(person, {'eolas_uri': EOLAS_URI_A})
        self.assertEqual(response.status_code, 302)

        linked_calls = self._calls_of_type(mock_loganne, 'contactLinked')
        self.assertEqual(len(linked_calls), 1, "contactLinked must fire exactly once")
        payload = linked_calls[0].args[0]
        self.assertEqual(payload['eolasUri'], EOLAS_URI_A)
        self.assertIsNone(payload['previousEolasUri'])

    def test_initial_link_also_fires_contact_updated(self):
        """contactUpdated also fires alongside contactLinked (no suppression)."""
        person = make_person('Alice')
        with patch('agents.loganne.loganneRequest') as mock_loganne:
            self._post_change(person, {'eolas_uri': EOLAS_URI_A})

        updated_calls = self._calls_of_type(mock_loganne, 'contactUpdated')
        self.assertEqual(len(updated_calls), 1, "contactUpdated must also fire")

    # ── Test 2: relink (URI → different URI) ─────────────────────────────────

    def test_relink_fires_contact_linked_with_previous_uri(self):
        """
        Changing eolas_uri from one URI to another fires contactLinked with
        previousEolasUri set to the old URI.
        """
        person = Person.objects.create(eolas_uri=EOLAS_URI_A)
        PersonName.objects.create(agent=person, name='Bob')
        with patch('agents.loganne.loganneRequest') as mock_loganne:
            response = self._post_change(person, {'eolas_uri': EOLAS_URI_B})
        self.assertEqual(response.status_code, 302)

        linked_calls = self._calls_of_type(mock_loganne, 'contactLinked')
        self.assertEqual(len(linked_calls), 1)
        payload = linked_calls[0].args[0]
        self.assertEqual(payload['eolasUri'], EOLAS_URI_B)
        self.assertEqual(payload['previousEolasUri'], EOLAS_URI_A)

    def test_relink_also_fires_contact_updated(self):
        """contactUpdated fires alongside contactLinked on a relink."""
        person = Person.objects.create(eolas_uri=EOLAS_URI_A)
        PersonName.objects.create(agent=person, name='Bob')
        with patch('agents.loganne.loganneRequest') as mock_loganne:
            self._post_change(person, {'eolas_uri': EOLAS_URI_B})

        updated_calls = self._calls_of_type(mock_loganne, 'contactUpdated')
        self.assertEqual(len(updated_calls), 1)

    # ── Test 3: unlink (URI → null) ───────────────────────────────────────────

    def test_unlink_fires_contact_unlinked_with_previous_uri(self):
        """
        Clearing eolas_uri fires contactUnlinked with previousEolasUri set
        to the URI that was just removed.
        """
        person = Person.objects.create(eolas_uri=EOLAS_URI_A)
        PersonName.objects.create(agent=person, name='Carol')
        with patch('agents.loganne.loganneRequest') as mock_loganne:
            response = self._post_change(person, {'eolas_uri': ''})
        self.assertEqual(response.status_code, 302)

        unlinked_calls = self._calls_of_type(mock_loganne, 'contactUnlinked')
        self.assertEqual(len(unlinked_calls), 1, "contactUnlinked must fire exactly once")
        payload = unlinked_calls[0].args[0]
        self.assertEqual(payload['previousEolasUri'], EOLAS_URI_A)

    def test_unlink_also_fires_contact_updated(self):
        """contactUpdated fires alongside contactUnlinked (no suppression)."""
        person = Person.objects.create(eolas_uri=EOLAS_URI_A)
        PersonName.objects.create(agent=person, name='Carol')
        with patch('agents.loganne.loganneRequest') as mock_loganne:
            self._post_change(person, {'eolas_uri': ''})

        updated_calls = self._calls_of_type(mock_loganne, 'contactUpdated')
        self.assertEqual(len(updated_calls), 1)

    # ── Test 4: no change ─────────────────────────────────────────────────────

    def test_no_event_when_eolas_uri_unchanged(self):
        """No contactLinked or contactUnlinked fires when eolas_uri is not modified."""
        person = Person.objects.create(eolas_uri=EOLAS_URI_A)
        PersonName.objects.create(agent=person, name='Dave')
        with patch('agents.loganne.loganneRequest') as mock_loganne:
            # Submit the form with eolas_uri unchanged
            self._post_change(person, {'eolas_uri': EOLAS_URI_A})

        linked_calls = self._calls_of_type(mock_loganne, 'contactLinked')
        unlinked_calls = self._calls_of_type(mock_loganne, 'contactUnlinked')
        self.assertEqual(linked_calls, [], "contactLinked must not fire when eolas_uri is unchanged")
        self.assertEqual(unlinked_calls, [], "contactUnlinked must not fire when eolas_uri is unchanged")

    def test_no_contact_linked_on_other_field_change(self):
        """Changing an unrelated field (bio) does not emit contactLinked or contactUnlinked."""
        person = Person.objects.create(eolas_uri=None, bio="")
        PersonName.objects.create(agent=person, name='Eve')
        with patch('agents.loganne.loganneRequest') as mock_loganne:
            self._post_change(person, {'bio': 'Updated bio text'})

        linked_calls = self._calls_of_type(mock_loganne, 'contactLinked')
        unlinked_calls = self._calls_of_type(mock_loganne, 'contactUnlinked')
        self.assertEqual(linked_calls, [])
        self.assertEqual(unlinked_calls, [])
