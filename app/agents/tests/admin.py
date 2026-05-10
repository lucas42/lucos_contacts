# -*- coding: utf-8 -*-
"""
Journey-level test scaffolding for Relationship admin functionality.

These tests drive admin URLs end-to-end using django.test.Client, asserting on
visible outcomes (rendered HTML, HTTP status codes, database state) rather than
calling model methods or admin class methods directly.

Sanity tests in this file exercise the stock Django admin for ``Relationship``
(registered in admin.py via ``admin.site.register(Relationship)`` with the
default ``ModelAdmin``).  This registration is the pre-authorised exception to
the "no production code changes" criterion in #699 — the architect's issue body
explicitly names registering ``Relationship`` in admin as the example of a
legitimate prerequisite change; the coordinator confirmed scope before it was
applied.

Admin tests that exercise ADR-0001 deletion-semantics behaviour — the custom
``RelationshipAdmin`` with its closure-check ``delete_view``, refusal page,
sibling-group bulk-confirm expansion, Loganne emission on admin delete, or the
inline delete-link routing introduced by ``can_delete = False`` — belong in
#700 and #701, alongside the production code that introduces those behaviours.
They are explicitly out of scope here.
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


class RelationshipAdminSanityTest(AdminJourneyTestCase):
	"""
	Sanity journey tests proving the harness drives Relationship admin URLs
	correctly.

	All three tests operate against the stock Django admin for ``Relationship``
	(bare registration, default ``ModelAdmin``).  The custom ``RelationshipAdmin``
	with ADR-0001 deletion semantics is not present on ``main`` and its tests
	belong in #700/#701.
	"""

	# ── Test 1: changelist GET ─────────────────────────────────────────────────

	def test_relationship_changelist_renders_seeded_row(self):
		"""
		GET the Relationship changelist → 200; rendered HTML contains the seeded
		relationship's string representation.

		``Relationship.__str__`` returns ``"subject – type – object"``, so the
		changelist row includes the names of both agents.

		Proves the harness authenticates and reaches the Relationship admin
		changelist view.
		"""
		alice = make_person('Alice')
		bob = make_person('Bob')
		Relationship.objects.create(subject=alice, object=bob, relationshipType='sibling')

		response = self.client.get(reverse('admin:agents_relationship_changelist'))
		self.assertEqual(response.status_code, 200)
		# The changelist uses Relationship.__str__ which includes both names
		self.assertContains(response, 'Alice')
		self.assertContains(response, 'Bob')

	# ── Test 2: change-form GET ────────────────────────────────────────────────

	def test_relationship_change_form_names_involved_agents(self):
		"""
		GET an individual Relationship change-form → 200; the rendered HTML
		names both agents involved in the relationship.

		The default ``ModelAdmin`` renders ``subject`` and ``object`` as select
		widgets, with the currently selected ``Person`` visible in the option
		list.

		Proves the harness can reach the change-form and that agent identities
		are present in the rendered output.
		"""
		alice = make_person('Alice')
		bob = make_person('Bob')
		rel = Relationship.objects.create(
			subject=alice, object=bob, relationshipType='sibling'
		)

		response = self.client.get(
			reverse('admin:agents_relationship_change', args=[rel.pk])
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Alice')
		self.assertContains(response, 'Bob')

	# ── Test 3: multi-step admin delete confirmation flow ─────────────────────

	def test_stock_django_admin_delete_journey(self):
		"""
		Drive the stock Django admin delete confirmation flow for a Relationship:

		1. GET the delete confirmation page → 200 with the standard
		   "Are you sure?" prompt.
		2. POST with ``post=yes`` to confirm → success; the targeted row is
		   absent from the database.

		This is the pre-#698 / pre-ADR-0001 delete behaviour: no closure check,
		no refusal, no sibling-group expansion.  The default ``ModelAdmin``
		calls ``obj.delete()`` directly.

		Proves the harness can drive a multi-step admin POST (GET confirmation
		→ POST confirm) through to a successful DB mutation.
		"""
		alice = make_person('Alice')
		bob = make_person('Bob')
		rel = Relationship.objects.create(
			subject=alice, object=bob, relationshipType='half-sibling'
		)
		# half-sibling is symmetric (creates an inverse) but not transitive,
		# so the target row itself is unambiguous for assertion.

		delete_url = reverse('admin:agents_relationship_delete', args=[rel.pk])

		# ── Step 1: GET delete confirmation page ─────────────────────────────
		response = self.client.get(delete_url)
		self.assertEqual(response.status_code, 200)

		# ── Step 2: confirm deletion ──────────────────────────────────────────
		response = self.client.post(delete_url, {'post': 'yes'}, follow=True)
		self.assertEqual(response.status_code, 200)

		self.assertFalse(
			Relationship.objects.filter(pk=rel.pk).exists(),
			"The targeted Relationship row must be absent after admin delete",
		)
