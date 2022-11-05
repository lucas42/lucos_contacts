# -*- coding: utf-8 -*-
from django.db import models
from django.utils import translation
from django.core.exceptions import ObjectDoesNotExist
from phonenumber_field.modelfields import PhoneNumberField
from .agent import Agent, AgentName

def getCurrentLang():
	cur_language = translation.get_language()
	if cur_language is None:
		return ""
	return cur_language[:2]


class BaseAccount(models.Model):
	agent = models.ForeignKey(Agent, blank=False, on_delete=models.CASCADE)
	active = models.BooleanField(default=True)
	class Meta:
		abstract = True

	@classmethod
	def getTypeByKey(cls, typeKey):
		accountTypes = {
			"facebook": FacebookAccount,
			"google": GoogleAccount,
			"phone": PhoneNumber,
			"email": EmailAddress,
			"googlecontact": GoogleContact,

			# HACK:Technically not an account, but also has an `.agent` relationship, so works for now
			"name": AgentName,
		}
		accountType = accountTypes.get(typeKey)
		if accountType is None:
			raise ObjectDoesNotExist("Can't find account of type "+str(typeKey))
		return accountType

	# Could use a django manager for these, but that'd require overwriting the manager on each
	@classmethod
	def get(cls, **kwargs):
		accountType = cls.getTypeByKey(kwargs.pop("type", None))
		return accountType.objects.get(**kwargs)

	@classmethod
	def get_or_create(cls, **kwargs):
		accountType = cls.getTypeByKey(kwargs.pop("type", None))
		return accountType.objects.get_or_create(**kwargs)



class PhoneNumber(BaseAccount):
	number = PhoneNumberField(blank=False)
	def __str__(self):
		if getCurrentLang() == 'ga':
			return 'Uimhir guathan '+self.agent.getName()
		return self.agent.getName()+"'s Phone Number"

class EmailAddress(BaseAccount):
	address = models.EmailField(max_length=255, blank=False)
	class Meta:
		verbose_name_plural = "Email Addresses"
	def __str__(self):
		if getCurrentLang() == 'ga':
			return u'Seolodh Ríomhphost '+self.agent.getName()
		return self.agent.getName()+"'s Email Address"

class PostalAddress(BaseAccount):
	address = models.CharField(max_length=255, blank=False)
	class Meta:
		verbose_name_plural = "Postal Addresses"
	def __str__(self):
		if getCurrentLang() == 'ga':
			return 'Seoladh '+self.agent.getName()
		return self.agent.getName()+"'s Address"

class FacebookAccount(BaseAccount):
	userid = models.PositiveBigIntegerField(blank=False)
	username = models.CharField(max_length=255, blank=True)
	def __str__(self):
		if getCurrentLang() == 'ga':
			return 'Cuntas Facebook '+self.agent.getName()
		return self.agent.getName()+"'s Facebook Account"

# An actual google acount, which can be logged into by the user
class GoogleAccount(BaseAccount):
	userid = models.CharField(max_length=255, blank=False)
	def __str__(self):
		if getCurrentLang() == 'ga':
			return 'Cuntas Google '+self.agent.getName()
		return self.agent.getName()+"'s Google Account"

# A contact from Google Contacts
class GoogleContact(BaseAccount):
	contactid = models.CharField(max_length=127, blank=False)
	def __str__(self):
		if getCurrentLang() == 'ga':
			return u'Teagmháil Google '+self.agent.getName()
		return self.agent.getName()+"'s Google Contact"

