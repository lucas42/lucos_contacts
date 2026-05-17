import json

from agents.models import *
from agents.models.relationship import RelationshipRefusedError, SiblingGroupExpansionRequired
from agents.models.closure import compute_closure
from django import forms
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from agents.loganne import contactCreated, contactUpdated, contactDeleted

class NameInline(admin.TabularInline):
	model = PersonName
	extra = 1
	min_num = 1
	verobse_name = "Name"
	verbose_name_plural = "Names"
	show_first = True

class AccountInline(admin.TabularInline):
	extra = 1
	min_num = 0

class PhoneInline(AccountInline):
	model = PhoneNumber

class EmailInline(AccountInline):
	model = EmailAddress

class AddressInline(AccountInline):
	model = PostalAddress

class FacebookAccountInline(AccountInline):
	model = FacebookAccount

class GoogleAccountInline(AccountInline):
	model = GoogleAccount

class GoogleContactInline(AccountInline):
	model = GoogleContact

class GooglePhotosProfileInline(AccountInline):
	model = GooglePhotosProfile

class RelationshipInline(admin.TabularInline):
	model = Relationship
	fk_name = 'subject'
	fields = ('relationshipType', 'object', 'delete_link')
	readonly_fields = ('delete_link',)
	autocomplete_fields = ['object']
	can_delete = False  # Deletions must go through RelationshipAdmin which enforces the closure-check rule

	def delete_link(self, obj):
		"""Render a delete link that routes through RelationshipAdmin's closure-checked delete view."""
		if obj.pk:
			url = reverse('admin:agents_relationship_delete', args=[obj.pk])
			return format_html('<a href="{}">Delete</a>', url)
		return ''
	delete_link.short_description = ''

class RomanticRelationshipForm(forms.ModelForm):
	romanticPartner = forms.ModelChoiceField(
		queryset=Person.objects.all(),
		required=True,
		label="Romantic Partner",
		widget=admin.widgets.AutocompleteSelect(RomanticRelationship._meta.get_field('personA'), admin.site),
	)

	class Meta:
		model = RomanticRelationship
		exclude = ("personA", "personB")

	def __init__(self, *args, **kwargs):
		self.current_agent = kwargs.pop('current_agent', None)
		super().__init__(*args, **kwargs)
		if self.current_agent:
			self.fields['romanticPartner'].queryset = Person.objects.exclude(pk=self.current_agent.pk)
			if self.instance.pk:
				self.fields['romanticPartner'].initial = self.instance.getOtherPerson(self.current_agent)
	def save(self, commit=True):
		# PersonA is set in the PersonAdmin save_formset, so just add personB here
		self.instance.personB = self.cleaned_data['romanticPartner']
		return super().save(commit=commit)

class RomanticRelationshipInline(admin.TabularInline):
	model = RomanticRelationship
	form = RomanticRelationshipForm
	extra = 1
	fk_name = 'personA'  # Needed by Django, but we try to override where needed

	def get_formset(self, request, obj=None, **kwargs):
		FormSet = super().get_formset(request, obj, **kwargs)

		class FormSetWithCurrentPerson(FormSet):
			def __init__(self, *args, **kwargs):
				kwargs['form_kwargs'] = {'current_agent': obj}
				super().__init__(*args, **kwargs)

			def get_queryset(self):
				return RomanticRelationship.objects.filter_person(obj)

		return FormSetWithCurrentPerson
	def get_fields(self, request, obj=None):
		all_fields = [f.name for f in self.model._meta.fields if f.name not in self.form.Meta.exclude]
		fields_order = ['romanticPartner'] + [f for f in all_fields if f != 'romanticPartner']
		return fields_order

class PersonAdminForm(forms.ModelForm):
	merge_into = forms.ModelChoiceField(
		queryset=Person.objects.all(),
		required=False,
		label="Merge into this person",
		widget=admin.widgets.AutocompleteSelect(RomanticRelationship._meta.get_field('personA'), admin.site),
	)

	class Meta:
		model = Person
		fields = '__all__'

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		if self.instance.pk:
			self.fields['merge_into'].queryset = Person.objects.exclude(pk=self.instance.pk)

class PersonAdmin(admin.ModelAdmin):
	form = PersonAdminForm
	actions = ['merge','delete_all_relationships']
	inlines = [
		NameInline,
		PhoneInline,
		EmailInline,
		AddressInline,
		FacebookAccountInline,
		GoogleAccountInline,
		GoogleContactInline,
		GooglePhotosProfileInline,
		RelationshipInline,
		RomanticRelationshipInline,
	]
	search_fields = ['_name', 'personname__name']
	list_max_show_all = 1000

	def _merge_two_agents(self, mainagent, secondary):
		"""Merge secondary person's data into mainagent, then delete secondary."""
		# For relationships, we need to be careful of duplicates.
		# Use queryset delete (bypasses model-level delete() override) so that
		# duplicate-removal is not subject to the closure-check rule.
		for rel in Relationship.objects.filter(subject=secondary):
			if Relationship.objects.filter(subject=mainagent, object=rel.object, relationshipType=rel.relationshipType).exists():
				Relationship.objects.filter(pk=rel.pk).delete()
			else:
				Relationship.objects.filter(pk=rel.pk).update(subject=mainagent)
		for rel in Relationship.objects.filter(object=secondary):
			if Relationship.objects.filter(subject=rel.subject, object=mainagent, relationshipType=rel.relationshipType).exists():
				Relationship.objects.filter(pk=rel.pk).delete()
			else:
				Relationship.objects.filter(pk=rel.pk).update(object=mainagent)

		RomanticRelationship.objects.filter(personA=secondary).update(personA=mainagent)
		RomanticRelationship.objects.filter(personB=secondary).update(personB=mainagent)
		ExternalPerson.objects.filter(agent=secondary).update(agent=mainagent)
		PersonName.objects.filter(agent=secondary).update(agent=mainagent)
		PhoneNumber.objects.filter(agent=secondary).update(agent=mainagent)
		EmailAddress.objects.filter(agent=secondary).update(agent=mainagent)
		PostalAddress.objects.filter(agent=secondary).update(agent=mainagent)
		FacebookAccount.objects.filter(agent=secondary).update(agent=mainagent)
		GoogleAccount.objects.filter(agent=secondary).update(agent=mainagent)
		GoogleContact.objects.filter(agent=secondary).update(agent=mainagent)
		GooglePhotosProfile.objects.filter(agent=secondary).update(agent=mainagent)
		secondary.delete()

	def merge(self, request, queryset):
		agents = queryset.order_by('id')
		if (agents.count() < 2):
			messages.error(request, "Merging a single object is futile")
			return
		mainagent = None
		for agent in agents:
			if not mainagent:
				mainagent = agent
			else:
				self._merge_two_agents(mainagent, agent)

	def delete_all_relationships(self, request, queryset):
		agents = queryset.order_by('id')
		for agent in agents:
			Relationship.objects.filter(subject=agent).delete()
			Relationship.objects.filter(object=agent).delete()

	def save_model(self, request, obj, form, change):
		super().save_model(request, obj, form, change)
		merge_into = form.cleaned_data.get('merge_into')
		if merge_into:
			self._merge_two_agents(obj, merge_into)

	def response_add(self, request, agent):
		res = super().response_add(request, agent)
		contactCreated(agent)
		return redirect(agent.get_absolute_url())
	def response_change(self, request, agent):
		res = super().response_change(request, agent)
		contactUpdated(agent)
		return redirect(agent.get_absolute_url())
	def delete_model(self, request, agent):
		# Get details from object before delete
		contact_name = str(agent)
		contact_id = agent.id
		contact_url = agent.get_absolute_url()
		super().delete_model(request, agent)
		contactDeleted(contact_name, contact_id, contact_url)

	def save_formset(self, request, form, formset, change):
		if isinstance(formset.model, RomanticRelationship):
			instances = formset.save(commit=False)
			for instance in instances:
				if not instance.personA_id:
					instance.personA = form.instance  # parent Person
				instance.save()
			formset.save_m2m()
		else:
			super().save_formset(request, form, formset, change)

admin.site.register(Person, PersonAdmin)


class RelationshipAdmin(admin.ModelAdmin):
	"""
	Admin interface for managing Relationship rows via the deletion journey.

	Registered with get_model_perms() returning {} so Relationships do NOT
	appear as a standalone item on the admin index — they are managed
	exclusively through the RelationshipInline on the Person change form.
	The registration exists solely to provide the custom delete_view URLs
	that the inline's delete-link routes through.

	Overrides delete_view to enforce the closure-check rule (ADR-0001).
	The GET path computes the staged set and closure check up front and
	renders the appropriate page directly — stock confirmation for clean
	deletions, bulk-delete confirmation when a sibling-aware expansion
	resolves the re-inference, or a dedicated refusal page when deletion
	is structurally impossible without first retracting a supporting fact.
	"""
	list_display = ('subject', 'relationshipType', 'object')
	list_filter = ('relationshipType',)
	search_fields = ['subject___name', 'object___name']

	def get_model_perms(self, request):
		"""
		Return empty permissions so Relationship does not appear on the admin
		index page.  The delete_view URLs are still accessible — they are
		linked from the RelationshipInline's delete_link field.
		"""
		return {}

	def get_urls(self):
		custom_urls = [
			path(
				'bulk-delete-confirm/',
				self.admin_site.admin_view(self.bulk_delete_confirmation_view),
				name='agents_relationship_bulk_delete_confirm',
			),
		]
		return custom_urls + super().get_urls()

	def delete_view(self, request, object_id, extra_context=None):
		"""
		GET-time decision: compute staged set and closure check, then render
		the appropriate page directly.

		- Clean: delegate to super().delete_view() — stock Django confirmation.
		- Expansion resolves re-inference: render bulk-delete confirmation directly.
		- Refused: render dedicated refusal page directly.

		POST (clean path via stock confirmation): delegate to super().delete_view().
		The underlying delete() raises RelationshipRefusedError or
		SiblingGroupExpansionRequired only if the graph changes between the
		GET and POST — treated as a race condition with a user-facing error.

		On all paths (success or error), redirects to the relationship subject's
		Person edit page rather than the Relationship changelist.

		Note: Django names this parameter ``object_id`` in the URL routing
		contract.  Internally we use ``relationship_id`` where possible to avoid
		confusion with ``Relationship.object`` (a Person FK).
		"""
		# Alias for clarity: Relationship has an `object` field (a Person FK),
		# so `object_id` is ambiguous.  `relationship_id` is the Relationship PK.
		relationship_id = object_id

		if request.method == 'GET':
			obj = self.get_object(request, relationship_id)
			if obj is None:
				return self._get_obj_does_not_exist_redirect(request, self.model._meta, relationship_id)

			staged = obj._build_staged_set()
			db_rows = frozenset(
				(rel.subject_id, rel.object_id, rel.relationshipType)
				for rel in Relationship.objects.all()
			)
			remaining = db_rows - staged
			re_inferred = staged & compute_closure(remaining)

			if not re_inferred:
				# Clean deletion — show stock Django confirmation
				return super().delete_view(request, relationship_id, extra_context=extra_context)

			# Try sibling-aware expansion (covers both transitive sibling
			# propagation and non-sibling rows implied by sibling connections).
			expanded = obj._compute_sibling_group_expansion(staged, db_rows)
			re_inferred_after = expanded & compute_closure(db_rows - expanded)

			if not re_inferred_after:
				# Expansion resolves the re-inference — render bulk-delete confirmation.
				is_sibling_only = all(rel_key == 'sibling' for _, _, rel_key in expanded)

				if is_sibling_only:
					# Build the full sibling group list for the "all recorded as
					# siblings" copy.
					extra_ids = set()
					for s, o, _ in expanded - staged:
						extra_ids.add(s)
						extra_ids.add(o)
					extra_ids -= {obj.subject_id, obj.object_id}
					extra_people = list(
						Person.objects.filter(pk__in=extra_ids).order_by('_name')
					)
					sibling_group = [obj.subject, obj.object] + extra_people
					supporting_rel_descriptions = []
				else:
					# Mixed expansion: show the co-inferred direct-type rows being deleted.
					# Strategy 2 stages (B, T, C) alongside (A, T, C) — display only the
					# direct direction (not its inverse) to avoid showing both directions.
					sibling_group = []
					extra_rows = expanded - staged
					target_rel_type = getRelationshipTypeByKey(obj.relationshipType)
					people_ids = set()
					for s_id, o_id, _ in extra_rows:
						people_ids.add(s_id)
						people_ids.add(o_id)
					people_names = {
						p.pk: p.getName()
						for p in Person.objects.filter(pk__in=people_ids)
					}
					supporting_rel_descriptions = [
						f"{people_names.get(s_id, f'Person #{s_id}')} "
						f"{target_rel_type.label} "
						f"{people_names.get(o_id, f'Person #{o_id}')}"
						for s_id, o_id, rel_key in sorted(extra_rows)
						if rel_key == obj.relationshipType
					]

				context = {
					**self.admin_site.each_context(request),
					'title': 'Confirm bulk deletion',
					'original_relationship': obj,
					'is_sibling_only': is_sibling_only,
					'sibling_group': sibling_group,
					'supporting_rel_descriptions': supporting_rel_descriptions,
					'staged_rows_count': len(expanded),
					'staged_rows_json': json.dumps([list(row) for row in expanded]),
					'subject_pk': obj.subject_id,
					'opts': self.model._meta,
				}
				return TemplateResponse(
					request,
					'admin/agents/relationship/bulk_delete_confirmation.html',
					context,
				)

			# Refused — render refusal page directly
			supporting_paths = obj._get_supporting_paths(remaining)
			context = {
				**self.admin_site.each_context(request),
				'title': "This relationship can't be deleted yet",
				'original_relationship': obj,
				'supporting_paths': supporting_paths,
				'opts': self.model._meta,
			}
			return TemplateResponse(
				request,
				'admin/agents/relationship/refused_deletion.html',
				context,
			)

		# POST — clean deletion path (post=yes from stock confirmation).
		# Capture subject_id before delegation so we can redirect to the person
		# page after deletion (the object is gone by the time Django redirects).
		obj = self.get_object(request, relationship_id)
		subject_id = obj.subject_id if obj else None

		try:
			result = super().delete_view(request, relationship_id, extra_context=extra_context)
			# On successful deletion Django issues a redirect — send the user
			# to the subject's Person page rather than the Relationship changelist.
			if isinstance(result, HttpResponseRedirect) and subject_id:
				return redirect(reverse('admin:agents_person_change', args=[subject_id]))
			return result
		except RelationshipRefusedError:
			messages.error(
				request,
				"This relationship can no longer be deleted because the relationship "
				"graph has changed since this page was loaded. Please try again.",
			)
		except SiblingGroupExpansionRequired:
			messages.error(
				request,
				"This relationship can no longer be deleted because the relationship "
				"graph has changed since this page was loaded. Please try again.",
			)

		if subject_id:
			return redirect(reverse('admin:agents_person_change', args=[subject_id]))
		return redirect(reverse('admin:agents_relationship_changelist'))

	def bulk_delete_confirmation_view(self, request):
		"""
		Custom view for sibling-aware bulk-delete confirmation.

		GET:  Not used — the confirmation page is rendered directly from delete_view.
		POST: Re-validates the staged set, performs the deletion, emits Loganne events,
		      then redirects to the subject's Person page.
		"""
		if request.method == 'POST':
			subject_pk = request.POST.get('subject_pk')

			def _person_redirect():
				if subject_pk:
					return redirect(reverse('admin:agents_person_change', args=[subject_pk]))
				return redirect(reverse('admin:agents_relationship_changelist'))

			if request.POST.get('confirm') == 'yes':
				staged_rows_json = request.POST.get('staged_rows', '[]')
				try:
					staged_list = json.loads(staged_rows_json)
					staged_rows = frozenset(tuple(row) for row in staged_list)
				except (ValueError, TypeError):
					messages.error(request, "Invalid deletion request.")
					return _person_redirect()

				# Re-run closure check before committing (guards against race conditions)
				db_rows = frozenset(
					(rel.subject_id, rel.object_id, rel.relationshipType)
					for rel in Relationship.objects.all()
				)
				remaining = db_rows - staged_rows
				re_inferred = staged_rows & compute_closure(remaining)

				if re_inferred:
					messages.error(
						request,
						"The deletion can no longer proceed — the relationship graph "
						"has changed since this page was loaded. Please try again.",
					)
					return _person_redirect()

				deleted_count = Relationship._perform_staged_deletion(staged_rows)

				messages.success(
					request,
					f"Deleted {deleted_count} relationship{'s' if deleted_count != 1 else ''}.",
				)
				return _person_redirect()

			# User cancelled
			return _person_redirect()

		# Direct GET to this URL — redirect to list
		return redirect(reverse('admin:agents_relationship_changelist'))


admin.site.register(Relationship, RelationshipAdmin)
