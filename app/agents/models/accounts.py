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
	is_primary = models.BooleanField(default=False)
	class Meta:
		verbose_name = _('email address')
		verbose_name_plural = _('email addresses')
		constraints = [
			# Backstop beneath the save() logic below - guarantees at most one *active*
			# primary email per person even on write paths that bypass save() (bulk
			# updates, future API writes).  Zero-primary is allowed (condition only
			# matches is_primary=True rows).
			models.UniqueConstraint(fields=['agent'], condition=models.Q(is_primary=True), name='unique_primary_email_per_agent'),
		]

	def save(self, *args, **kwargs):
		# is_primary => active: an inactive row can never be the (effective) primary,
		# since serializePerson only ever looks at active addresses.  If this row has
		# been deactivated, clear its primary flag regardless of what was passed in -
		# this may leave the person with no primary until one is (re-)chosen.
		if not self.active:
			self.is_primary = False

		# If this agent has no active primary email, and this row is active, make it
		# the primary (auto-first) - mirrors PersonName.save(), scoped to active rows.
		if self.active:
			primaryCount = EmailAddress.objects.filter(agent=self.agent, is_primary=True, active=True).count()
			if primaryCount == 0:
				self.is_primary = True

		# If this is the primary email, ensure none of the other emails for this agent
		# are primary any more (unset-others-then-set, so a single save never leaves
		# two rows holding it at once).
		if self.is_primary:
			queryset = EmailAddress.objects.filter(agent=self.agent)
			if self.pk:
				queryset = queryset.exclude(pk=self.pk)
			queryset.update(is_primary=False)
		super().save(*args, **kwargs)

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

