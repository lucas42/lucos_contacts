# -*- coding: utf-8 -*-
from django.db import models, router
from django.core.exceptions import ObjectDoesNotExist, ValidationError
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

	# Named so validate_constraints() below can skip re-checking it pre-save
	# without silently swallowing any other constraint EmailAddress might gain.
	PRIMARY_CONSTRAINT_NAME = 'unique_primary_email_per_agent'

	def clean(self):
		super().clean()
		# is_primary => active, surfaced as an explicit validation error rather
		# than save()'s silent auto-clear (see below) - so an admin user who
		# marks an inactive email primary (or deactivates a currently-primary
		# one without also unsetting is_primary) gets a clear explanation
		# instead of the checkbox quietly reverting with no feedback.
		# save() still auto-clears for any write path that skips validation
		# (bulk updates, scripts, migrations) - this is purely about giving a
		# human editing the admin form a chance to fix their intent.
		if self.is_primary and not self.active:
			raise ValidationError({'is_primary': _("An inactive email address can't be set as primary - reactivate it, or unset primary, first.")})

	def validate_constraints(self, exclude=None):
		# Skip Django's automatic pre-save check of PRIMARY_CONSTRAINT_NAME
		# (Model.full_clean() -> validate_constraints(), added in Django 4.1).
		# That check queries the CURRENT (pre-transaction) DB state for each
		# instance independently, before ANY form in a formset has saved - so
		# swapping the primary between two of a person's own emails in a single
		# admin-inline-formset submission always fails it: at validation time the
		# old primary still shows as is_primary=True, so the new primary's own
		# validation sees a "duplicate" that was never actually going to exist
		# once both forms save (Django surfaces this as "Constraint
		# unique_primary_email_per_agent is violated").
		#
		# The invariant itself is enforced correctly elsewhere: save() below
		# clears every other row's is_primary before setting this one
		# (unset-others-then-set), so at no SQL statement boundary do two rows
		# ever hold is_primary=True - the swap genuinely is safe in one save.
		# The DB constraint remains as the real backstop for write paths that
		# bypass save() entirely (bulk updates, future API writes); only this
		# redundant, overly-eager pre-save check is skipped. Any other
		# constraint added to this model in future is still validated normally.
		using = router.db_for_write(self.__class__, instance=self)
		errors = {}
		for constraint in self._meta.constraints:
			if constraint.name == self.PRIMARY_CONSTRAINT_NAME:
				continue
			try:
				constraint.validate(self.__class__, self, exclude=exclude, using=using)
			except ValidationError as e:
				if getattr(e, 'code', None) == 'unique' and len(constraint.fields) == 1:
					errors.setdefault(constraint.fields[0], []).append(e)
				else:
					errors = e.update_error_dict(errors)
		if errors:
			raise ValidationError(errors)

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

