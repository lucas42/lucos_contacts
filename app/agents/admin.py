from agents.models import *
from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect
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

class RomanticRelationshipForm(forms.ModelForm):
	romanticPartner = forms.ModelChoiceField(
		queryset=Person.objects.all(),
		required=True,
		label="Romantic Partner",
		widget=admin.widgets.AutocompleteSelect(RomanticRelationship._meta.get_field('personB'), admin.site),
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

class PersonAdmin(admin.ModelAdmin):
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
				# For relationships, we need to be careful of duplicates
				for rel in Relationship.objects.filter(subject=agent):
					if Relationship.objects.filter(subject=mainagent, object=rel.object, relationshipType=rel.relationshipType).exists():
						rel.delete()
					else:
						Relationship.objects.filter(pk=rel.pk).update(subject=mainagent)
				for rel in Relationship.objects.filter(object=agent):
					if Relationship.objects.filter(subject=rel.subject, object=mainagent, relationshipType=rel.relationshipType).exists():
						rel.delete()
					else:
						Relationship.objects.filter(pk=rel.pk).update(object=mainagent)

				RomanticRelationship.objects.filter(personA=agent).update(personA=mainagent)
				RomanticRelationship.objects.filter(personB=agent).update(personB=mainagent)
				ExternalPerson.objects.filter(agent=agent).update(agent=mainagent)
				PersonName.objects.filter(agent=agent).update(agent=mainagent)
				PhoneNumber.objects.filter(agent=agent).update(agent=mainagent)
				EmailAddress.objects.filter(agent=agent).update(agent=mainagent)
				PostalAddress.objects.filter(agent=agent).update(agent=mainagent)
				FacebookAccount.objects.filter(agent=agent).update(agent=mainagent)
				GoogleAccount.objects.filter(agent=agent).update(agent=mainagent)
				GoogleContact.objects.filter(agent=agent).update(agent=mainagent)
				GooglePhotosProfile.objects.filter(agent=agent).update(agent=mainagent)

				agent.delete()
	def delete_all_relationships(self, request, queryset):
		agents = queryset.order_by('id')
		for agent in agents:
			Relationship.objects.filter(subject=agent).delete()
			Relationship.objects.filter(object=agent).delete()
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
