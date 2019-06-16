from django.db import migrations
from django.core.exceptions import ImproperlyConfigured  
from agents.models import *

def forwards(apps, schema_editor):
	googlecontact = AccountType.objects.get(id=16)
	accounts = Account.objects.filter(type=googlecontact)
	for legacyAccount in Account.objects.all():
		account = None
		if legacyAccount.type.id == 16:
			account = GoogleContact(agent=legacyAccount.agent, contactid=legacyAccount.userid)
		if legacyAccount.type.id == 15:
			account = GoogleAccount(agent=legacyAccount.agent, userid=legacyAccount.userid)
		if legacyAccount.type.id == 9:
			account = EmailAddress(agent=legacyAccount.agent, address=legacyAccount.userid)
		if account is None:
			raise ImproperlyConfigured("Unexpected legacy account type:"+legacyAccount.type.getLabel())
		account.save()
		legacyAccount.delete()

class Migration(migrations.Migration):

	dependencies = [
		('agents', '0011_auto_20190616_2033'),
	]

	operations = [
		migrations.RunPython(forwards),
	]