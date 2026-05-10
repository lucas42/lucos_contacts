from agents.models import *
from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
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
	fields = ('relationshipType', 'object')
	autocomplete_fields = ['object']
	can_delete = False  # Deletions must go through RelationshipAdmin which enforces the closure-check rule

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
	Admin interface for directly managing Relationship rows.

	Overrides the standard delete_view to enforce the closure-check rule
	(ADR-0001).  When a deletion is refused, the user sees the supporting
	inference paths.  When a sibling-group expansion is needed and passes
	the extended closure check, the user is routed to a bulk-delete
	confirmation page.
	"""
	list_display = ('subject', 'relationshipType', 'object')
	list_filter = ('relationshipType',)
	search_fields = ['subject___name', 'object___name']

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
		Override to intercept RelationshipRefusedError and
		SiblingGroupExpansionRequired raised by Relationship.delete().
		"""
		import json
		from agents.models.relationship import RelationshipRefusedError, SiblingGroupExpansionRequired

		if request.method == 'POST' and request.POST.get('post') == 'yes':
			try:
				return super().delete_view(request, object_id, extra_context=extra_context)
			except SiblingGroupExpansionRequired as exc:
				# Route to the bulk-delete confirmation page.
				# Serialize staged_rows so the confirmation form can echo them back.
				staged_list = [list(row) for row in exc.staged_rows]
				members_info = [
					{'id': p.pk, 'name': p.getName()}
					for p in exc.sibling_members
				]
				obj = self.get_object(request, object_id)
				context = {
					**self.admin_site.each_context(request),
					'title': 'Confirm bulk deletion',
					'original_relationship': obj,
					'sibling_members': exc.sibling_members,
					'staged_rows_count': len(exc.staged_rows),
					'staged_rows_json': json.dumps(staged_list),
					'opts': self.model._meta,
				}
				return TemplateResponse(
					request,
					'admin/agents/relationship/bulk_delete_confirmation.html',
					context,
				)
			except RelationshipRefusedError as exc:
				messages.error(request, str(exc))
				return redirect(
					reverse(
						'admin:agents_relationship_change',
						args=[object_id],
					)
				)

		return super().delete_view(request, object_id, extra_context=extra_context)

	def bulk_delete_confirmation_view(self, request):
		"""
		Custom view for sibling-group bulk-delete confirmation.

		GET:  Not used — we render the confirmation page directly from delete_view.
		POST: Performs the deletion and emits Loganne events.
		"""
		import json
		from agents.models.relationship import RelationshipRefusedError, SiblingGroupExpansionRequired

		if request.method == 'POST':
			if request.POST.get('confirm') == 'yes':
				staged_rows_json = request.POST.get('staged_rows', '[]')
				try:
					staged_list = json.loads(staged_rows_json)
					staged_rows = frozenset(tuple(row) for row in staged_list)
				except (ValueError, TypeError):
					messages.error(request, "Invalid deletion request.")
					return redirect(reverse('admin:agents_relationship_changelist'))

				# Re-run closure check before committing.
				from agents.models.closure import compute_closure
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
					return redirect(reverse('admin:agents_relationship_changelist'))

				deleted_count = Relationship._perform_staged_deletion(staged_rows)

				messages.success(
					request,
					f"Deleted {deleted_count} relationship{'s' if deleted_count != 1 else ''}.",
				)
				return redirect(reverse('admin:agents_relationship_changelist'))

			# User cancelled
			return redirect(reverse('admin:agents_relationship_changelist'))

		# Direct GET to this URL — redirect to list
		return redirect(reverse('admin:agents_relationship_changelist'))


admin.site.register(Relationship, RelationshipAdmin)
