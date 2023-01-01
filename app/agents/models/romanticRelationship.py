from django.db import models
from .agent import Agent, dayChoices, monthChoices
from django.utils.translation import gettext_lazy as _
from datetime import date

class RomanticRelationship(models.Model):
	MILESTONE_CHOICES = [
		('dating', _('Dating')),
		('cohabitation', _('Cohabitation')),
		('engaged', _('Engaged')),
		('married', _('Married')),
	]
	members = models.ManyToManyField(Agent)
	active = models.BooleanField(default=True)

	# Maximum milestone acheived before the relationship ended
	milestone = models.CharField(choices=MILESTONE_CHOICES, blank=False, default='dating', max_length=127)
	start_day = models.IntegerField(choices=dayChoices(), blank=True, null=True)
	start_month = models.IntegerField(choices=monthChoices(), blank=True, null=True)
	start_year = models.IntegerField(blank=True, null=True)
	end_day = models.IntegerField(choices=dayChoices(), blank=True, null=True)
	end_month = models.IntegerField(choices=monthChoices(), blank=True, null=True)
	end_year = models.IntegerField(blank=True, null=True)
	wedding_day = models.IntegerField(choices=dayChoices(), blank=True, null=True)
	wedding_month = models.IntegerField(choices=monthChoices(), blank=True, null=True)
	wedding_year = models.IntegerField(blank=True, null=True)

	def save(self, *args, **kwargs):

		# If the end of the relationship has passed, then it's no longer active
		if dateHasPassed(self.end_year, self.end_month, self.end_day):
			self.active = False

		# Try to update the milestone based on the wedding date info
		if self.wedding_year or self.wedding_month or self.wedding_day:
			weddingHasPassed = dateHasPassed(self.wedding_year, self.wedding_month, self.wedding_day)
			if weddingHasPassed:
				self.milestone = 'married'
			if weddingHasPassed is False:
				self.milestone = 'engaged'

			# If there's some info about wedding date, but not enough to be sure if it's happened,
			# then set milestone to engaged, unless it's already at married.
			if weddingHasPassed is None and self.milestone != 'married':
				self.milestone = 'engaged'
		super(RomanticRelationship, self).save(*args, **kwargs)

	def __str__(self):
		joinSymbol = "❤️" if self.active else "💔"
		memberNames = self.members.values_list('_name', flat=True)
		return (" "+joinSymbol+" ").join(memberNames)

# Takes a year, month and day (any of which may be None) and tries to determine if that date has passed yet
# Returns True if the date is in the past (or is today).
# Returns False if the date is in the future.
# Returns None if there's not enough infomartion to tell.
def dateHasPassed(year, month, day):
	currentYear = date.today().year
	currentMonth = date.today().month
	currentDay = date.today().day
	if not year:
		return None
	if currentYear > year:
		return True
	if currentYear < year:
		return False
	if not month:
		return None
	if currentMonth > month:
		return True
	if currentMonth < month:
		return False
	if not day:
		return None
	if currentDay >= day:
		return True
	return False