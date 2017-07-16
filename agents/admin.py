from agents.models import *
from django.contrib import admin

class AccountInline(admin.StackedInline):
	model = Account
	extra = 0

class PhoneInline(admin.TabularInline):
	model = PhoneNumber
	extra = 0
	min_num = 1

class AddressInline(admin.TabularInline):
	model = PostalAddress
	extra = 0
	min_num = 1

class RelationshipInline(admin.TabularInline):
	model = Relationship
	fk_name = 'object'
	fields = ('type', 'subject')

class AgentAdmin(admin.ModelAdmin):
    actions = ['merge']
    inlines = [
    	PhoneInline,
    	AddressInline,
    	AccountInline,
    	RelationshipInline
    ]
    def merge(self, request, queryset):
		agents = queryset.order_by('id')
		if (agents.count() < 2):
			#messages.error(request, "Merging a single object is futile") # requires django 1.2
			self.message_user(request, "Merging a single object is futile")
			return
		mainagent = None
		for agent in agents:
			if not mainagent:
				mainagent = agent
			else:
				Relationship.objects.filter(subject=agent).update(subject=mainagent)
				Relationship.objects.filter(object=agent).update(object=mainagent)
				Account.objects.filter(agent=agent).update(agent=mainagent)
				ExternalAgent.objects.filter(agent=agent).update(agent=mainagent)
				agent.delete()
    
class RelationshipAdmin(admin.ModelAdmin):
	fields = ('subject', 'type', 'object')
	list_display = ('subject', 'type', 'object')
	list_display_links = ('subject', 'type', 'object')
	ordering = ['subject']
	
class RelationshipTypeConnectionAdmin(admin.ModelAdmin):
	list_display = ('inferred_relation_type', 'relation_type_a', 'relation_type_b')
	list_display_links = ['inferred_relation_type']

admin.site.register(Agent, AgentAdmin)
admin.site.register(Account)
admin.site.register(PhoneNumber)
admin.site.register(PostalAddress)
admin.site.register(Relationship, RelationshipAdmin)
admin.site.register(AccountType)
admin.site.register(RelationshipType)
admin.site.register(RelationshipTypeConnection, RelationshipTypeConnectionAdmin)
