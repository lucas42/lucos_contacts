# -*- coding: utf-8 -*-
from django.db import models
from django.core.exceptions import ObjectDoesNotExist
from phonenumber_field.modelfields import PhoneNumberField
from .agent import Person, PersonName
from django.utils.translation import gettext_lazy as _

class BaseAccount(models.Model):
	agent = models.ForeignKey(Person, blank=False, on_delete=models.CASCADE)
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
			"googlephotos": GooglePhotosProfile,

			# HACK:Technically not an account, but also has an `.agent` relationship, so works for now
			"name": PersonName,
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

	def __str__(self):
		return _('%(name)s\'s %(type)s') % {
			'name': self.agent.getName(),
			'type': str(self._meta.verbose_name).title(),
		}

class PhoneNumber(BaseAccount):
	number = PhoneNumberField(blank=False)
	class Meta:
		verbose_name = _('phone number')
		verbose_name_plural = _('phone numbers')
	def __str__(self):
		return BaseAccount.__str__(self)

class EmailAddress(BaseAccount):
	address = models.EmailField(max_length=255, blank=False)
	class Meta:
		verbose_name = _('email address')
		verbose_name_plural = _('email addresses')

class PostalAddress(BaseAccount):
	address = models.CharField(max_length=255, blank=False)
	class Meta:
		verbose_name = _('postal address')
		verbose_name_plural = _('postal addresses')

class FacebookAccount(BaseAccount):
	userid = models.PositiveBigIntegerField(blank=False)
	username = models.CharField(max_length=255, blank=True)
	class Meta:
		verbose_name = _('facebook account')
		verbose_name_plural = _('facebook accounts')

# An actual google acount, which can be logged into by the user
class GoogleAccount(BaseAccount):
	userid = models.CharField(max_length=255, blank=False)
	class Meta:
		verbose_name = _('google account')
		verbose_name_plural = _('google accounts')

# A contact from Google Contacts
class GoogleContact(BaseAccount):
	contactid = models.CharField(max_length=127, blank=False)
	class Meta:
		verbose_name = _('google contact')
		verbose_name_plural = _('google contacts')

# A Person Tagged in Google Photos
class GooglePhotosProfile(BaseAccount):
	person_id = models.PositiveBigIntegerField(blank=False)
	cluster_media_key = models.CharField(max_length=255, blank=True)
	search_path = models.CharField(max_length=255, blank=True)
	class Meta:
		verbose_name = _('google photos profile')
		verbose_name_plural = _('google photos profiles')
	def __str__(self):
		return _('Photos tagged with %(name)s') % {
			'name': self.agent.getName(),
		}

