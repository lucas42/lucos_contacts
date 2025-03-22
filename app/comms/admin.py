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

class OccasionListAdmin(admin.ModelAdmin):
	filter_horizontal = ('gave_card_to', 'received_card_from')
	inlines = [
		PresentInline
	]

admin.site.register(OccasionList, OccasionListAdmin)

class PresentAdmin(admin.ModelAdmin):
	filter_horizontal = ('agents',)
	form = PresentForm

admin.site.register(Present, PresentAdmin)

class BirthdayPresentForm(PresentForm):
	class Meta:
		model = BirthdayPresent
		fields = ('agents', 'year', 'description')
		widgets = {
			'agents': forms.Select,
		}
		labels = {
			'agents': _('Whose birthday it was'),
			'description': _('What I gave them'),
		}
		help_texts = {
			'year': _("The calendar year of the birthday the present was for (which is usually, but not necessarily, the year the present was given)"),
		}

class BirthdayPresentAdmin(admin.ModelAdmin):
	form = BirthdayPresentForm

admin.site.register(BirthdayPresent, BirthdayPresentAdmin)
