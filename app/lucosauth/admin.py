from django.contrib import admin
from lucosauth.models import ApiUser

class ApiUserAdmin(admin.ModelAdmin):
	fields = ('system', 'apikey')

admin.site.register(ApiUser, ApiUserAdmin)