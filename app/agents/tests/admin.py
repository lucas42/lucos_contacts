# -*- coding: utf-8 -*-
"""
Journey-level tests for Relationship admin functionality.

Relationships are managed exclusively through the inline on the Person admin
change form — there are no standalone Relationship index or edit pages.

The three tests in ``RelationshipInlineJourneyTest`` verify:

1. The Person changelist renders and the harness is correctly authenticated.
2. The Person change form renders the RelationshipInline with seeded data.
3. A Relationship can be deleted via the inline POST flow.

The tests in ``RelationshipAdminDeletionJourneyTest`` exercise ADR-0001
deletion-semantics behaviour — the custom ``RelationshipAdmin`` with its
GET-time closure-check ``delete_view``, refusal page, sibling-group
bulk-confirm expansion, Loganne emission on admin delete, and the inline
delete-link routing introduced by ``can_delete = False``.
"""

import json
import re
from unittest.mock import patch

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
	- The ``_post_data_from_response`` helper for building POST data from a
	  Person change-form GET response.
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

	def _post_data_from_response(self, response):
		"""
		Build a POST data dict from a Person change-form GET response.

		Extracts management form data and existing instance field values from
		each inline formset in the response context.  The returned dict can be
		used directly as a base for a POST to the same change URL.

		Callers layer their intended mutations (e.g. ``DELETE`` flags) on top
		of the returned dict before posting.

		Implementation note: ``RelationshipInline.fk_name = 'subject'`` and
		``Relationship.subject`` carries ``related_name='subject'``, so Django
		sets the inline formset prefix to ``'subject'`` (from
		``ForeignKey.related_query_name()``).  This is invisible from outside
		but explains why the management-form keys look like ``subject-0-DELETE``
		rather than the perhaps-expected ``relationship_set-0-DELETE``.
		"""
		data = {'merge_into': ''}
		for inline_admin_formset in response.context['inline_admin_formsets']:
			fs = inline_admin_formset.formset
			prefix = fs.prefix
			data[f'{prefix}-TOTAL_FORMS'] = str(len(fs.forms))
			data[f'{prefix}-INITIAL_FORMS'] = str(fs.initial_form_count())
			data[f'{prefix}-MIN_NUM_FORMS'] = str(fs.min_num)
			data[f'{prefix}-MAX_NUM_FORMS'] = str(fs.max_num)
			# Iterate ALL forms (initial AND extra): extra forms that have
			# BooleanField defaults (e.g. ``active=True``) need those defaults
			# present in the POST dict, otherwise ``has_changed()`` returns True
			# (initial=True vs submitted=absent/False) → Django validates the
			# incomplete extra form → required-field errors on blank rows.
			for i, form in enumerate(fs.forms):
				for field_name in form.fields:
					value = form[field_name].value()
					# Exclude None and False: None means no value; False means
					# an unchecked checkbox which must be absent from POST.
					if value is not None and value is not False:
						data[f'{prefix}-{i}-{field_name}'] = value
		return data


class RelationshipInlineJourneyTest(AdminJourneyTestCase):
	"""
	Journey tests for Relationship editing through the Person admin inline.

	Relationships have no standalone index or edit pages in Django admin; they
	are managed exclusively via the ``RelationshipInline`` on the Person change
	form.

	These tests prove the harness can authenticate, reach the Person admin
	change form, read inline Relationship data, and drive a multi-step admin
	POST that deletes a Relationship via the inline.
	"""

	# ── Test 1: Person changelist ──────────────────────────────────────────────

	def test_person_changelist_renders_seeded_person(self):
		"""
		GET the Person changelist → 200; rendered HTML contains the seeded
		person's name.

		Proves the harness authenticates and reaches the Person admin
		changelist view.
		"""
		make_person('Alice')

		response = self.client.get(reverse('admin:agents_person_changelist'))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Alice')

	# ── Test 2: Person change form with RelationshipInline ────────────────────

	def test_person_change_form_shows_relationship_inline(self):
		"""
		GET the Person change form → 200; rendered HTML contains the names of
		both agents involved in the seeded Relationship via the
		``RelationshipInline``.

		The inline renders an ``object`` autocomplete field whose option list
		includes all People — so both agents' names appear in the rendered HTML.

		Proves the harness reaches the change form and that the inline renders
		relationship data correctly.
		"""
		alice = make_person('Alice')
		bob = make_person('Bob')
		Relationship.objects.create(subject=alice, object=bob, relationshipType='half-sibling')

		response = self.client.get(
			reverse('admin:agents_person_change', args=[alice.pk])
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Alice')
		self.assertContains(response, 'Bob')

	# ── Test 3: inline delete flow ────────────────────────────────────────────

	def test_inline_relationship_delete_ignores_checkbox(self):
		"""
		Drive the inline Relationship POST flow via the Person change form with
		a DELETE flag set and verify the relationship is NOT deleted.

		Since ADR-0001, ``RelationshipInline.can_delete = False`` — deletions
		must go through ``RelationshipAdmin.delete_view``, not through the
		stock inline-formset DELETE checkbox path.  Django's ``BaseFormSet``
		ignores DELETE flags when ``can_delete=False``.

		This test proves the harness can still drive a multi-step admin POST
		and documents the new invariant: the stock inline DELETE path is
		intentionally disabled.

		``half-sibling`` is symmetric (creates an inverse row with Bob as
		subject) but not transitive, so the assertion on ``rel.pk`` is
		unambiguous — only the Alice→Bob row is targeted.
		"""
		alice = make_person('Alice')
		bob = make_person('Bob')
		# half-sibling is symmetric — creates an inverse row (Bob→Alice) but is
		# not transitive.  We only assert on rel.pk so the inverse is irrelevant.
		rel = Relationship.objects.create(
			subject=alice, object=bob, relationshipType='half-sibling'
		)

		change_url = reverse('admin:agents_person_change', args=[alice.pk])

		# ── Step 1: GET to extract management-form data ───────────────────────
		get_response = self.client.get(change_url)
		self.assertEqual(get_response.status_code, 200)

		# ── Step 2: build POST data (no DELETE flag possible — can_delete=False) ─
		post_data = self._post_data_from_response(get_response)

		# Attempt to set a DELETE flag even though the inline has can_delete=False.
		# Django's BaseFormSet ignores this; it's included here only to document
		# that the flag is not honoured.
		for inline_admin_formset in get_response.context['inline_admin_formsets']:
			fs = inline_admin_formset.formset
			if fs.model is Relationship:
				prefix = fs.prefix
				for i, form in enumerate(fs.initial_forms):
					if form.instance.pk == rel.pk:
						post_data[f'{prefix}-{i}-DELETE'] = 'on'
						break
				break

		# ── Step 3: POST and verify relationship is NOT deleted ───────────────
		post_response = self.client.post(change_url, post_data, follow=True)
		self.assertEqual(post_response.status_code, 200)

		self.assertTrue(
			Relationship.objects.filter(pk=rel.pk).exists(),
			"With can_delete=False, the inline DELETE flag must have no effect — "
			"the relationship row must still exist after the POST.",
		)


class RelationshipAdminDeletionJourneyTest(AdminJourneyTestCase):
	"""
	Journey tests for the ADR-0001 relationship deletion journey.

	These tests drive the RelationshipAdmin delete_view end-to-end, asserting
	on the GET-time routing decision (which page is rendered), the POST
	outcomes (DB state, Loganne events), and structural invariants (single h1,
	correct form action).

	Three deletion scenarios are exercised:

	- **Clean**: Alice parent Bob (no re-inference after deletion) → stock
	  Django confirmation → POST → success, row gone, Loganne emitted.
	- **Expansion**: Alice sibling Bob + Bob sibling Carol (deletion would be
	  re-inferred; sibling-group expansion resolves it) → bulk-delete
	  confirmation rendered directly → POST → success, all sibling rows gone.
	- **Refusal**: Alice parent Bob inferred from (Alice sibling Carol) +
	  (Carol parent Bob) → refusal page rendered directly, supporting path
	  listed.
	"""

	# ── Helpers ───────────────────────────────────────────────────────────────

	def _delete_url(self, rel):
		"""Return the RelationshipAdmin delete URL for a given Relationship."""
		return reverse('admin:agents_relationship_delete', args=[rel.pk])

	# ── Test 1: Inline delete-link routing ────────────────────────────────────

	def test_inline_delete_link_routes_to_relationship_admin(self):
		"""
		The RelationshipInline renders a "Delete" link for each existing row
		that points to RelationshipAdmin's delete view, not a stock DELETE
		checkbox path.

		Proves ``can_delete = False`` is in effect (no inline checkbox) and
		the ``delete_link`` readonly field renders the correct URL.
		"""
		alice = make_person('Alice')
		bob = make_person('Bob')
		rel = Relationship.objects.create(subject=alice, object=bob, relationshipType='half-sibling')

		change_url = reverse('admin:agents_person_change', args=[alice.pk])
		response = self.client.get(change_url)
		self.assertEqual(response.status_code, 200)

		content = response.content.decode()
		delete_url = self._delete_url(rel)

		# The inline must render a link pointing to RelationshipAdmin's delete view.
		self.assertIn(
			delete_url, content,
			"RelationshipInline must contain a link to RelationshipAdmin.delete_view",
		)
		self.assertIn(
			'>Delete<', content,
			"RelationshipInline must render 'Delete' link text",
		)

		# There must be no DELETE checkbox for the Relationship inline
		# (can_delete=False suppresses the checkbox entirely).
		self.assertNotIn(
			'subject-0-DELETE',
			content,
			"RelationshipInline must not render a DELETE checkbox (can_delete=False)",
		)

	# ── Test 2: GET-path decision — clean ─────────────────────────────────────

	def test_clean_deletion_renders_stock_confirmation_and_deletes_on_post(self):
		"""
		When deleting a parent/child relationship with no re-inference path:

		- GET → stock Django delete confirmation page (contains ``post=yes`` form input).
		- POST with ``post=yes`` → relationship deleted from DB.
		- Loganne ``relationshipDeleted`` event emitted after commit.
		"""
		alice = make_person('Alice')
		bob = make_person('Bob')
		# parent creates its inverse (child) automatically
		rel = Relationship.objects.create(subject=alice, object=bob, relationshipType='parent')
		inverse_rel = Relationship.objects.get(subject=bob, object=alice, relationshipType='child')

		delete_url = self._delete_url(rel)

		# ── GET: should render stock Django confirmation ───────────────────────
		get_response = self.client.get(delete_url)
		self.assertEqual(get_response.status_code, 200)

		# Stock confirmation contains a hidden input with name="post" and value="yes"
		self.assertContains(
			get_response, 'name="post"',
			msg_prefix="GET should render stock Django confirmation (contains post=yes form input)",
		)
		# Must not render the bulk-delete confirmation heading
		self.assertNotContains(
			get_response, 'Confirm bulk deletion',
			msg_prefix="Stock confirmation must not contain bulk-delete heading",
		)

		# Single h1 on the stock confirmation page
		h1_count = get_response.content.decode().count('<h1')
		self.assertEqual(h1_count, 1, "Stock confirmation page must have exactly one <h1>")

		# ── POST: perform the deletion ────────────────────────────────────────
		with patch('agents.loganne.loganneRequest') as mock_loganne:
			with self.captureOnCommitCallbacks(execute=True):
				post_response = self.client.post(delete_url, {'post': 'yes'})

		self.assertEqual(post_response.status_code, 302, "POST should redirect after deletion")

		# Both the asserted row and its inverse must be gone
		self.assertFalse(
			Relationship.objects.filter(pk=rel.pk).exists(),
			"Alice-parent-Bob must be deleted",
		)
		self.assertFalse(
			Relationship.objects.filter(pk=inverse_rel.pk).exists(),
			"Bob-child-Alice (inverse) must also be deleted",
		)

		# Loganne must have fired at least one relationshipDeleted event
		loganne_calls = [
			call for call in mock_loganne.call_args_list
			if call.args and call.args[0].get('type') == 'relationshipDeleted'
		]
		self.assertGreater(
			len(loganne_calls), 0,
			"At least one relationshipDeleted Loganne event must be emitted",
		)

	# ── Test 3: GET-path decision — refusal ───────────────────────────────────

	def test_refusal_renders_dedicated_page_with_supporting_paths(self):
		"""
		When deleting a relationship that would be re-inferred from other facts
		in the graph (here: Alice parent Bob, implied by Alice sibling Carol +
		Carol parent Bob):

		- GET → dedicated refusal page rendered directly (not a messages.error toast).
		- Rendered HTML contains at least one non-empty supporting-path entry.
		- Rendered HTML does NOT contain a ``post=yes`` form input (no delete path).
		"""
		carol = make_person('Carol')
		bob = make_person('Bob')
		alice = make_person('Alice')

		# Carol parent Bob (asserted)
		Relationship.objects.create(subject=carol, object=bob, relationshipType='parent')
		# Alice sibling Carol (asserted; also infers Alice parent Bob via sibling+parent rule)
		Relationship.objects.create(subject=alice, object=carol, relationshipType='sibling')

		# The inferred Alice-parent-Bob row
		inferred_rel = Relationship.objects.get(subject=alice, object=bob, relationshipType='parent')

		delete_url = self._delete_url(inferred_rel)

		response = self.client.get(delete_url)
		self.assertEqual(response.status_code, 200)

		# Must not show the stock confirmation form
		self.assertNotContains(
			response, 'name="post"',
			msg_prefix="Refusal page must not contain a post=yes form input",
		)
		# Must not show the bulk-delete confirmation
		self.assertNotContains(
			response, 'name="confirm"',
			msg_prefix="Refusal page must not contain a bulk-confirm form input",
		)
		# Must render the dedicated refusal page title
		self.assertContains(
			response, "can't be deleted yet",
			msg_prefix="Refusal page must include the 'can't be deleted yet' page title",
		)
		# Must contain at least one supporting-path entry naming the relevant people
		content = response.content.decode()
		self.assertIn(
			'Alice', content,
			"Refusal page must name Alice in a supporting path",
		)
		self.assertIn(
			'Carol', content,
			"Refusal page must name Carol in a supporting path",
		)

		# Single h1 on the refusal page
		h1_count = content.count('<h1')
		self.assertEqual(h1_count, 1, "Refusal page must have exactly one <h1>")

	# ── Test 4: GET-path decision — expansion ─────────────────────────────────

	def test_expansion_renders_bulk_confirmation_directly_and_deletes_on_post(self):
		"""
		When deleting a sibling relationship whose deletion would be re-inferred
		due to transitive propagation (Alice sibling Bob, Bob sibling Carol):

		- GET → bulk-delete confirmation page rendered directly (no stock
		  confirmation in between).
		- Rendered output names the affected sibling-group member (Carol).
		- POST with ``confirm=yes`` and the staged rows → all affected rows deleted.
		"""
		alice = make_person('Alice')
		bob = make_person('Bob')
		carol = make_person('Carol')

		# Alice sibling Bob creates Bob sibling Alice (symmetric)
		alice_bob_rel = Relationship.objects.create(
			subject=alice, object=bob, relationshipType='sibling'
		)
		# Bob sibling Carol creates Carol sibling Bob; transitivity creates
		# Alice sibling Carol and Carol sibling Alice
		Relationship.objects.create(subject=bob, object=carol, relationshipType='sibling')

		delete_url = self._delete_url(alice_bob_rel)

		# ── GET: must render bulk-delete confirmation, not stock confirmation ──
		get_response = self.client.get(delete_url)
		self.assertEqual(get_response.status_code, 200)

		# Must NOT show stock Django confirmation
		self.assertNotContains(
			get_response, 'name="post"',
			msg_prefix="Expansion path must skip stock confirmation (no post=yes input)",
		)
		# Must show bulk-delete confirmation heading
		self.assertContains(
			get_response, 'Confirm bulk deletion',
			msg_prefix="Expansion path must render bulk-delete confirmation page",
		)
		# Carol must be named as an affected sibling-group member
		self.assertContains(
			get_response, 'Carol',
			msg_prefix="Bulk confirmation must name the affected sibling-group member Carol",
		)

		# Single h1 on the bulk-delete confirmation page
		h1_count = get_response.content.decode().count('<h1')
		self.assertEqual(h1_count, 1, "Bulk confirmation page must have exactly one <h1>")

		# ── Test 5: Form action targets the bulk handler URL ──────────────────
		bulk_confirm_url = reverse('admin:agents_relationship_bulk_delete_confirm')
		self.assertContains(
			get_response,
			f'action="{bulk_confirm_url}"',
			msg_prefix="Form action must target the bulk handler URL",
		)

		# ── POST: extract staged_rows from the response and perform deletion ──
		content = get_response.content.decode()
		# Extract the staged_rows JSON from the hidden input
		staged_rows_match = re.search(
			r'name="staged_rows" value="([^"]*)"', content
		)
		self.assertIsNotNone(staged_rows_match, "Response must contain staged_rows hidden input")
		staged_rows_json = staged_rows_match.group(1).replace('&quot;', '"')

		post_response = self.client.post(
			bulk_confirm_url,
			{'confirm': 'yes', 'staged_rows': staged_rows_json},
		)
		self.assertEqual(post_response.status_code, 302, "POST should redirect after bulk deletion")

		# All Alice-sibling-* and *-sibling-Alice rows must be gone
		self.assertFalse(
			Relationship.objects.filter(subject=alice).exists(),
			"All Alice-subject sibling rows must be deleted",
		)
		self.assertFalse(
			Relationship.objects.filter(object=alice).exists(),
			"All Alice-object sibling rows must be deleted",
		)
		# Bob sibling Carol and Carol sibling Bob remain (not in Alice's sibling group)
		self.assertTrue(
			Relationship.objects.filter(subject=bob, object=carol, relationshipType='sibling').exists(),
			"Bob-sibling-Carol must survive the bulk deletion",
		)
		self.assertTrue(
			Relationship.objects.filter(subject=carol, object=bob, relationshipType='sibling').exists(),
			"Carol-sibling-Bob must survive the bulk deletion",
		)
