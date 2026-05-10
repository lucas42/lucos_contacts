# -*- coding: utf-8 -*-
"""
Journey-level tests for Relationship admin deletion.

Each test drives the deletion flow through admin URLs end-to-end using
django.test.Client, asserting on visible outcomes (rendered HTML or the
messages framework) rather than calling model methods directly.

These tests exist to catch regressions in the admin layer — form actions,
redirect chains, template rendering, exception handlers — that are invisible
to the unit tests in models.py.
"""

import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.messages import get_messages, constants as message_constants
from django.test import Client, TestCase
from django.urls import reverse

from agents.models import Person, PersonName, Relationship
from lucosauth.models import LucosUser


class RelationshipAdminDeletionTest(TestCase):
    """
    Journey-level tests for RelationshipAdmin.delete_view and
    bulk_delete_confirmation_view.
    """

    def setUp(self):
        # Create a LucosUser to authenticate as for admin access.
        # LucosUser.has_perm grants 'agents.*' so all admin operations succeed.
        self.admin_person = Person.objects.create()
        self.admin_user = LucosUser.objects.create(agent=self.admin_person)
        # Django admin log (django_admin_log) has a FK to auth_user.  The
        # LucosAuthBackend.authenticate() does the same create() to satisfy it.
        User.objects.create(id=self.admin_user.id)
        self.client = Client()
        self.client.force_login(
            self.admin_user,
            backend='lucosauth.models.LucosAuthBackend',
        )

    def _delete_url(self, rel):
        return reverse('admin:agents_relationship_delete', args=[rel.pk])

    def _bulk_confirm_url(self):
        return reverse('admin:agents_relationship_bulk_delete_confirm')

    # ── Test 1: inline delete-link routing ────────────────────────────────────

    def test_inline_delete_link_routes_to_relationship_admin(self):
        """
        The RelationshipInline on the Person change page renders a delete link
        (not a DELETE checkbox) that points to RelationshipAdmin's delete_view.

        Guards against accidental regression of the can_delete=False decision:
        if can_delete were flipped back to True, Django would render a checkbox
        instead, bypassing the closure-check rule entirely.
        """
        alice = Person.objects.create()
        bob = Person.objects.create()
        rel = Relationship.objects.create(
            subject=alice, object=bob, relationshipType='sibling'
        )

        change_url = reverse('admin:agents_person_change', args=[alice.pk])
        response = self.client.get(change_url)
        self.assertEqual(response.status_code, 200)

        # The delete link must point to RelationshipAdmin's delete_view
        expected_delete_url = reverse(
            'admin:agents_relationship_delete', args=[rel.pk]
        )
        self.assertContains(response, expected_delete_url)

        # No Django inline DELETE checkbox — can_delete must remain False
        self.assertNotContains(response, 'name="relationship_set-0-DELETE"')

    # ── Test 2: clean deletion ─────────────────────────────────────────────────

    def test_clean_deletion_succeeds(self):
        """
        A relationship that is not re-inferred by the remaining graph can be
        deleted via the admin URL. After following the redirect chain, the
        row is absent from the DB and a success message is present.
        """
        alice = Person.objects.create()
        bob = Person.objects.create()
        # half-sibling is symmetric but not transitive — no third-party inference.
        # With only two people, neither row is re-inferred after deletion.
        Relationship.objects.create(
            subject=alice, object=bob, relationshipType='half-sibling'
        )
        target = Relationship.objects.get(
            subject=alice, object=bob, relationshipType='half-sibling'
        )

        with patch('agents.loganne.loganneRequest') as mock_loganne:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    self._delete_url(target),
                    {'post': 'yes'},
                    follow=True,
                )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Relationship.objects.filter(
                subject=alice, object=bob, relationshipType='half-sibling'
            ).exists(),
            "The targeted row must be deleted",
        )
        # Loganne must emit at least one event for the deletion
        self.assertGreater(
            mock_loganne.call_count, 0,
            "At least one Loganne event must be emitted on successful deletion",
        )
        # Django admin adds a success message (level SUCCESS = 25)
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(
            any(m.level == message_constants.SUCCESS for m in msgs),
            f"Expected a success-level message, got: {[(m.level, str(m)) for m in msgs]}",
        )

    # ── Test 3: inverse cascade ────────────────────────────────────────────────

    def test_inverse_cascade_deletes_both_rows(self):
        """
        Deleting (A, parent, B) via the admin URL also deletes the inverse
        (B, child, A). Both rows must be absent from the DB after the admin
        journey completes, and the success page must be reached.
        """
        alice = Person.objects.create()
        bob = Person.objects.create()
        Relationship.objects.create(
            subject=alice, object=bob, relationshipType='parent'
        )
        # Inference creates the inverse: (bob, child, alice)
        self.assertTrue(
            Relationship.objects.filter(
                subject=bob, object=alice, relationshipType='child'
            ).exists(),
            "Inference should have created the inverse child row",
        )

        target = Relationship.objects.get(
            subject=alice, object=bob, relationshipType='parent'
        )

        with patch('agents.loganne.loganneRequest'):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    self._delete_url(target),
                    {'post': 'yes'},
                    follow=True,
                )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Relationship.objects.filter(
                subject=alice, object=bob, relationshipType='parent'
            ).exists(),
            "The parent row must be deleted",
        )
        self.assertFalse(
            Relationship.objects.filter(
                subject=bob, object=alice, relationshipType='child'
            ).exists(),
            "The inverse child row must also be deleted via cascade",
        )

    # ── Test 4: refusal — multi-relation chain ────────────────────────────────

    def test_refusal_multi_relation_shows_non_empty_inference_paths(self):
        """
        When (A, aunt/uncle, C) is implied by (A, parent, B) + (B, sibling, C),
        attempting to delete the aunt/uncle row via the admin URL must:
          - redirect back to the relationship change page (not delete it)
          - render an error message containing the supporting inference path(s)
          - leave the row in the database

        This is the assertion that would have caught the "empty supporting-path
        list" bug noted in the issue.
        """
        alice = Person.objects.create()
        bob = Person.objects.create()
        carol = Person.objects.create()

        Relationship.objects.create(
            subject=alice, object=bob, relationshipType='parent'
        )
        Relationship.objects.create(
            subject=bob, object=carol, relationshipType='sibling'
        )
        # SetInference: parent + sibling → aunt/uncle
        self.assertTrue(
            Relationship.objects.filter(
                subject=alice, object=carol, relationshipType='aunt/uncle'
            ).exists(),
            "Inference should have created alice aunt/uncle carol",
        )

        target = Relationship.objects.get(
            subject=alice, object=carol, relationshipType='aunt/uncle'
        )

        response = self.client.post(
            self._delete_url(target),
            {'post': 'yes'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)

        # Row must still be in the database — refusal means nothing was deleted
        self.assertTrue(
            Relationship.objects.filter(
                subject=alice, object=carol, relationshipType='aunt/uncle'
            ).exists(),
            "The refused row must remain in the database",
        )

        # The error message must be present and contain at least one inference path.
        # RelationshipRefusedError._make_message() prefixes each path with "– ".
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(
            any("can't be removed" in m for m in msgs),
            f"Expected a refusal message, got: {msgs}",
        )
        self.assertTrue(
            any('–' in m for m in msgs),
            f"Refusal message must include at least one inference path (prefixed '– '), got: {msgs}",
        )

    # ── Test 5: sibling-group expansion ───────────────────────────────────────

    def test_sibling_group_expansion_journey(self):
        """
        When (A, sib, C) is implied transitively via B, the deletion journey is:
          1. POST to delete_view → renders the bulk-confirm page (not a redirect)
             with the affected sibling-group member (B) named in the page body.
          2. POST to bulk_delete_confirmation_view with confirm=yes and the
             staged_rows from the confirmation page → redirects to the changelist.
          3. All sibling rows involving A are gone from the database.
        """
        alice = Person.objects.create()
        # Give Bob a name so we can assert it appears on the confirmation page
        bob = Person.objects.create()
        PersonName.objects.create(agent=bob, name='Bob')
        carol = Person.objects.create()

        Relationship.objects.create(
            subject=alice, object=bob, relationshipType='sibling'
        )
        Relationship.objects.create(
            subject=bob, object=carol, relationshipType='sibling'
        )
        # Transitive: (alice, sibling, carol) is now inferred
        target = Relationship.objects.get(
            subject=alice, object=carol, relationshipType='sibling'
        )

        # ── Step 1: initial delete attempt → bulk confirmation page ──────────
        response = self.client.post(
            self._delete_url(target),
            {'post': 'yes'},
        )
        self.assertEqual(
            response.status_code, 200,
            "Expected the bulk confirmation page (200), not a redirect",
        )
        self.assertTemplateUsed(
            response,
            'admin/agents/relationship/bulk_delete_confirmation.html',
        )
        # Bob (the sibling mediator) must be named on the confirmation page
        self.assertContains(response, 'Bob')
        # The form must POST to the bulk-confirm URL, not back to the delete URL.
        # A missing action= would send the form to the current URL (the single-item
        # delete URL), where delete_view sees no post=yes and falls through to the
        # single-item confirmation page — breaking the flow entirely.
        self.assertContains(response, self._bulk_confirm_url())
        # staged_rows_json must be in the template context for the hidden field
        self.assertIn('staged_rows_json', response.context)
        staged_rows_json = response.context['staged_rows_json']

        # ── Step 2: confirm the bulk deletion ────────────────────────────────
        with patch('agents.loganne.loganneRequest'):
            with self.captureOnCommitCallbacks(execute=True):
                confirm_response = self.client.post(
                    self._bulk_confirm_url(),
                    {'confirm': 'yes', 'staged_rows': staged_rows_json},
                    follow=True,
                )

        self.assertEqual(confirm_response.status_code, 200)

        # ── Step 3: all sibling rows for alice must be gone ───────────────────
        self.assertFalse(
            Relationship.objects.filter(
                subject=alice, relationshipType='sibling'
            ).exists(),
            "alice must have no remaining sibling relationships as subject",
        )
        self.assertFalse(
            Relationship.objects.filter(
                object=alice, relationshipType='sibling'
            ).exists(),
            "No sibling row should point to alice as object",
        )

        # A success message must be present (use level check — message text is locale-dependent)
        msgs = list(get_messages(confirm_response.wsgi_request))
        self.assertTrue(
            any(m.level == message_constants.SUCCESS for m in msgs),
            f"Expected a success-level message, got: {[(m.level, str(m)) for m in msgs]}",
        )
