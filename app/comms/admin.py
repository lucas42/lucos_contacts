from comms.models import *
from django.contrib import admin

class ChristmasListAdmin(admin.ModelAdmin):
	filter_horizontal = ('gave_card_to','received_card_from')

admin.site.register(ChristmasList, ChristmasListAdmin)