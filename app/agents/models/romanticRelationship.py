from django.db import models
from .agent import Agent, dayChoices, monthChoices
from django.utils.translation import gettext_lazy as _
from datetime import date
from django.db.models import Q

class RomanticRelationshipQuerySet(models.QuerySet):
	def filter_person(self, person):
		return self.filter(
			Q(personA=person) |
			Q(personB=person)
		)
	def filter_people(self, person1, person2):
		return self.filter(
			Q(personA=person1, personB=person2) |
			Q(personA=person2, personB=person1)
		)
	def filter_starred(self): # Only include romantic relationships where either of the people are starred
		return self.filter(
			Q(personA__starred=True) |
			Q(personB__starred=True)
		)

class RomanticRelationship(models.Model):
	MILESTONE_CHOICES = [
		('dating', _('Dating')),
		('cohabitation', _('Cohabitation')),
		('engaged', _('Engaged')),
		('married', _('Married')),
	]
	personA = models.ForeignKey(Agent, related_name='personA', blank=False, on_delete=models.CASCADE)
	personB = models.ForeignKey(Agent, related_name='personB', blank=False, on_delete=models.CASCADE)
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

	objects = RomanticRelationshipQuerySet.as_manager()

	def save(self, *args, **kwargs):

		# Store person A & B in a consistent order, based on ID
		if self.personA_id > self.personB_id:
			self.personA, self.personB = self.personA, self.personB

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
		return self.personA.getName()+" "+joinSymbol+" "+self.personB.getName()

	# Put romantic relationships to the top of relationships lists
	def getPriority(self):
		return -1

	def getRelationshipLabel(self):
		if self.milestone == 'married':
			return _('Spouse')
		if self.milestone == 'engaged':
			# Translators: Using this in a gender-neutral sense here.
			# Whilst there's often a spelling difference based on gender, there seems to be
			# growing acceptance of using the previously male form in a gender-neutral way now
			return _('Fiancé')
		return _('Partner')

	# Returns a string containing the first names of the members, separated by ampersands
	def getFirstNames(self):
		return self.personA.getName().split()[0]+" & "+self.personB.getName().split()[0]

	# Given a person, figures out who the other person in the relationship is
	# (If given a person who isn't in the relationship, will return the personA)
	def getOtherPerson(self, person):
		if (person == self.personA):
			return self.personB
		else:
			return self.personA

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