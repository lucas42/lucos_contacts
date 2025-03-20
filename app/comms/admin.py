from comms.models import *
from django.contrib import admin
from django import forms


class PresentForm(forms.ModelForm):
	class Meta:
		model = Present
		fields = '__all__'
		widgets = {
			'was_given': forms.RadioSelect
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

class BirthdayPresentAdmin(admin.ModelAdmin):
	filter_horizontal = ('agents',)
	exclude = ('occasion',)
	form = PresentForm

admin.site.register(BirthdayPresent, BirthdayPresentAdmin)
