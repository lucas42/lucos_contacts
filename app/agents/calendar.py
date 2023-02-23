from django.shortcuts import render
from agents.models import *
from django.urls import reverse
from datetime import date
from django.utils.translation import gettext as _
from django.contrib.humanize.templatetags.humanize import ordinal
from django.contrib.auth.decorators import login_required

def getBirthdays():
	agentlist = Agent.objects.filter(starred=True).exclude(day_of_birth__isnull=True).exclude(month_of_birth__isnull=True)
	birthdays = []
	for agent in agentlist.distinct():
		date = nextOccurence(agent.day_of_birth, agent.month_of_birth)
		if agent.year_of_birth:
			age = date.year - agent.year_of_birth
			label = _('%(name)s\'s %(count)s Birthday') % {
				'name': agent.getName(),
				'count': ordinal(age)
			}
		else:
			label = _('%(name)s\'s Birthday') % {
				'name': agent.getName()
			}
		birthdays.append({
			'date': date,
			'label': label,
			'link': agent.get_absolute_url(),
		})
	return birthdays

def getDeathdays():
	agentlist = Agent.objects.filter(starred=True).exclude(day_of_death__isnull=True).exclude(month_of_death__isnull=True)
	deathdays = []
	for agent in agentlist.distinct():
		date = nextOccurence(agent.day_of_death, agent.month_of_death)
		label = _('%(name)s\'s Deathday') % {'name': agent.getName()}
		deathdays.append({
			'date': date,
			'label': label,
			'link': agent.get_absolute_url(),
		})
	return deathdays

def getWeddings():
	relationships = RomanticRelationship.objects.filter(active=True, members__starred=True).exclude(wedding_day__isnull=True).exclude(wedding_month__isnull=True)
	weddingdays = []
	for relationship in relationships.distinct():
		date = nextOccurence(relationship.wedding_day, relationship.wedding_month)
		if relationship.milestone == 'married':
			if relationship.wedding_year:
				age = date.year - relationship.wedding_year
				label = _('%(names)s\'s %(count)s Anniversary') % {
					'names': relationship.getFirstNames(),
					'count': ordinal(age)
				}
			else:
				label = _('%(names)s\'s Anniversary') % {
					'names': relationship.getFirstNames()
				}
		elif relationship.milestone == 'engaged':
			# If the wedding year isn't this upcoming year, then ignore
			if date.year != relationship.wedding_year:
				continue
			label = _('%(names)s\'s Wedding') % {
				'names': relationship.getFirstNames()
			}
		else:
			continue
		weddingdays.append({
			'date': date,
			'label': label,
			'link': relationship.get_absolute_url(),
		})
	return weddingdays


def getEvents():
	events = getBirthdays() + getDeathdays() + getWeddings()
	events.sort(key=lambda event: event['date'])
	return events

# Returns boolean.
# True if the next instance of this date is next year.
# False if there's a remaining this year (including today).
def isNextYear(day, month):
	currentDay = date.today().day
	currentMonth = date.today().month
	if month > currentMonth:
		return False
	if month < currentMonth:
		return True
	return (day < currentDay)

# Returns a date object set to the next time this event will occur
# Should never return a date in the past, but may return today's date.
def nextOccurence(day, month):
	year = date.today().year
	if isNextYear(day, month):
		year += 1
	return date(year, month, day)

@login_required
def renderCalendar(request):
	return render(None, 'agents/index.html', {
		'template': 'agents/calendar.html',
		'title': _("Contacts Calendar"),
		'list': 'calendar',
		'addurl': reverse('admin:agents_agent_add'),
		'events': getEvents(),
	})