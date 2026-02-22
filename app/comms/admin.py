from comms.models import *
from django.contrib import admin
from django import forms
from django.utils.translation import gettext_lazy as _


class PresentForm(forms.ModelForm):
	class Meta:
		model = Present
		fields = '__all__'
		widgets = {
			'was_given': forms.RadioSelect,
		}
class PresentInline(admin.TabularInline):
	model = Present
	form = PresentForm
	extra = 1
	autocomplete_fields = ['agents']

class OccasionListAdmin(admin.ModelAdmin):
	autocomplete_fields = ['gave_card_to', 'received_card_from']
	inlines = [
		PresentInline
	]

admin.site.register(OccasionList, OccasionListAdmin)

class PresentAdmin(admin.ModelAdmin):
	autocomplete_fields = ['agents']
	form = PresentForm

admin.site.register(Present, PresentAdmin)

class BirthdayPresentForm(PresentForm):
	class Meta:
		model = BirthdayPresent
		fields = ('agents', 'year', 'description')
		labels = {
			'agents': _('Whose birthday it was'),
			'description': _('What I gave them'),
		}

class BirthdayPresentAdmin(admin.ModelAdmin):
	form = BirthdayPresentForm
	autocomplete_fields = ['agents']

admin.site.register(BirthdayPresent, BirthdayPresentAdmin)
