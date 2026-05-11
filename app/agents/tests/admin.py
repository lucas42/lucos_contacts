# -*- coding: utf-8 -*-
"""
Journey-level test scaffolding for Relationship admin functionality.

Relationships are managed exclusively through the inline on the Person admin
change form — there are no standalone Relationship index or edit pages.

These tests drive Person admin URLs end-to-end using django.test.Client,
asserting on visible outcomes (rendered HTML, HTTP status codes, database
state) rather than calling model methods or admin class methods directly.

The three tests in ``RelationshipInlineJourneyTest`` verify:

1. The Person changelist renders and the harness is correctly authenticated.
2. The Person change form renders the RelationshipInline with seeded data.
3. A Relationship can be deleted via the inline POST flow.

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

	def test_inline_relationship_delete_removes_row(self):
		"""
		Drive the inline Relationship delete flow via the Person change form:

		1. GET the Person change form to extract inline management-form data.
		2. POST back with the ``DELETE`` checkbox set for the target Relationship
		   row.
		3. The targeted Relationship is absent from the database.

		This is the stock Django inline-formset delete behaviour: no closure
		check, no refusal, no sibling-group expansion.  The default inline
		formset calls ``obj.delete()`` directly on each row marked for deletion.

		``half-sibling`` is symmetric (creates an inverse row with Bob as
		subject) but not transitive, so the assertion on ``rel.pk`` is
		unambiguous — only the Alice→Bob row is targeted.

		The custom ADR-0001 deletion semantics (closure check, refusal page,
		sibling-group expansion, Loganne emission) belong in #700/#701.

		Proves the harness can drive a multi-step admin POST through to a
		successful DB mutation.
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

		# ── Step 2: build POST data and mark the Relationship for deletion ────
		post_data = self._post_data_from_response(get_response)

		# Find the RelationshipInline formset by model and mark rel for deletion.
		for inline_admin_formset in get_response.context['inline_admin_formsets']:
			fs = inline_admin_formset.formset
			if fs.model is Relationship:
				prefix = fs.prefix
				for i, form in enumerate(fs.initial_forms):
					if form.instance.pk == rel.pk:
						post_data[f'{prefix}-{i}-DELETE'] = 'on'
						break
				break

		# ── Step 3: POST and verify ───────────────────────────────────────────
		post_response = self.client.post(change_url, post_data, follow=True)
		self.assertEqual(post_response.status_code, 200)

		self.assertFalse(
			Relationship.objects.filter(pk=rel.pk).exists(),
			"The targeted Relationship row must be absent after inline delete",
		)
