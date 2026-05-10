# -*- coding: utf-8 -*-
"""
Journey-level test scaffolding for admin functionality touching relationships.

These tests drive admin URLs end-to-end using django.test.Client, asserting on
visible outcomes (rendered HTML, HTTP status codes, database state) rather than
calling model methods or admin class methods directly.

Sanity tests in this file exercise the admin behaviour already present on
``main`` (pre-#698): the standard Django admin for ``Person``, which exposes
relationships via ``RelationshipInline`` on the change form.

Admin tests that exercise ADR-0001 deletion-semantics behaviour — closure
checks, the refusal page, sibling-group bulk-confirm expansion, Loganne
emission on admin delete, or the inline delete-link routing introduced by
``can_delete = False`` — belong in #700 and #701, alongside the production
code that introduces those behaviours.  They are explicitly out of scope here.

Note: ``Relationship`` is not registered directly in Django admin on ``main``
(only via ``RelationshipInline`` on ``PersonAdmin``).  Relationship-specific
admin URLs (changelist, change-form, standalone delete confirmation) require
that registration, which is tracked as prerequisite infrastructure for #700.
"""

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from agents.models import Person, PersonName, Relationship
from lucosauth.models import LucosUser


def make_person(name=None):
	"""Create a ``Person``, optionally giving them a ``PersonName``."""
	person = Person.objects.create()
	if name:
		PersonName.objects.create(agent=person, name=name)
	return person


class AdminJourneyTestCase(TestCase):
	"""
	Base class for admin journey tests.

	Provides:

	- An authenticated ``django.test.Client`` logged in as a ``LucosUser``.
	  Any ``LucosUser`` instance passes Django admin's ``is_staff`` check
	  because ``LucosUser.is_staff`` is a regular method (not a property);
	  accessing it as an attribute returns a truthy bound-method object.
	- A companion native ``User`` row with the same primary key, required to
	  satisfy the ``django_admin_log`` foreign key (this mirrors the HACK
	  comment in ``LucosAuthBackend.authenticate``).
	- The ``make_person`` helper for creating test agents with optional names.
	"""

	def setUp(self):
		self.admin_person = Person.objects.create()
		self.admin_user = LucosUser.objects.create(agent=self.admin_person)
		# HACK: satisfy django_admin_log FK — mirrors LucosAuthBackend.authenticate
		User.objects.create(id=self.admin_user.id)
		self.client = Client()
		self.client.force_login(
			self.admin_user,
			backend='lucosauth.models.LucosAuthBackend',
		)


class PersonAdminSanityTest(AdminJourneyTestCase):
	"""
	Sanity journey tests proving the harness drives Django admin URLs correctly.

	All three tests operate through the ``Person`` admin (``PersonAdmin``),
	which exposes relationship data via ``RelationshipInline``.  They verify:

	1. The harness authenticates and reaches admin views.
	2. The admin change form renders inline relationship rows.
	3. The harness can drive a multi-step admin POST (GET confirmation →
	   POST confirm) through to completion and assert on final DB state.
	"""

	# ── Test 1: changelist GET ─────────────────────────────────────────────────

	def test_person_changelist_renders_seeded_row(self):
		"""
		GET the Person changelist → 200; rendered HTML contains the seeded
		person's name.

		Proves the harness authenticates correctly and reaches real admin views.
		"""
		make_person('Alice')
		response = self.client.get(reverse('admin:agents_person_changelist'))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Alice')

	# ── Test 2: change-form GET with RelationshipInline ───────────────────────

	def test_person_change_form_renders_relationship_inline(self):
		"""
		GET a Person's change-form → 200; the rendered HTML includes the
		``RelationshipInline`` section showing the seeded relationship type.

		Proves the harness can reach the change-form view and that the inline
		renders relationship data correctly.
		"""
		alice = make_person('Alice')
		bob = make_person('Bob')
		Relationship.objects.create(subject=alice, object=bob, relationshipType='sibling')

		response = self.client.get(
			reverse('admin:agents_person_change', args=[alice.pk])
		)
		self.assertEqual(response.status_code, 200)
		# The RelationshipInline renders a <select> for relationshipType;
		# 'sibling' must appear as a selected/available option.
		self.assertContains(response, 'sibling')

	# ── Test 3: multi-step admin delete journey ────────────────────────────────

	def test_person_admin_delete_journey(self):
		"""
		Drive the stock Django admin delete confirmation flow for a Person:

		1. GET the delete confirmation page → 200 with the standard
		   "Are you sure?" prompt.
		2. POST with ``post=yes`` to confirm → success; the Person and their
		   Relationship rows are gone from the database.

		This is the pre-#698 delete behaviour: no closure check, no refusal,
		no sibling-group expansion.  Proves the harness can drive a multi-step
		admin POST through to a successful DB mutation.

		``PersonAdmin.delete_model`` calls ``contactDeleted`` → ``loganneRequest``
		internally, but ``loganneRequest`` returns immediately when
		``LOGANNE_ENDPOINT`` is not set (which is the case in the test
		environment), so no mocking is required.
		"""
		alice = make_person('Alice')
		bob = make_person('Bob')
		Relationship.objects.create(subject=alice, object=bob, relationshipType='sibling')

		delete_url = reverse('admin:agents_person_delete', args=[alice.pk])

		# ── Step 1: GET delete confirmation page ─────────────────────────────
		response = self.client.get(delete_url)
		self.assertEqual(response.status_code, 200)

		# ── Step 2: confirm deletion ──────────────────────────────────────────
		response = self.client.post(delete_url, {'post': 'yes'}, follow=True)
		self.assertEqual(response.status_code, 200)

		self.assertFalse(
			Person.objects.filter(pk=alice.pk).exists(),
			"Alice must be absent from the database after admin delete",
		)
		self.assertFalse(
			Relationship.objects.filter(
				subject=alice, object=bob, relationshipType='sibling'
			).exists(),
			"Alice's relationships must be cascade-deleted",
		)
