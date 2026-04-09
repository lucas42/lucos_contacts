from django.shortcuts import render
from agents.models import *
from django.urls import reverse
from datetime import date, datetime
import calendar as calendar_module
from django.http import HttpResponse
from django.utils.translation import gettext as _
from django.contrib.humanize.templatetags.humanize import ordinal
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from lucosauth.decorators import calendar_auth
from icalendar import Calendar, Event
from lucosauth.envvars import get_calendar_key
from django.conf import settings


# Returns the start of the rolling window (today minus 1 month).
# Handles month-end edge cases (e.g. March 31 -> Feb 28/29).
def _windowStart():
	today = date.today()
	month = today.month - 1
	year = today.year
	if month == 0:
		month = 12
		year -= 1
	day = min(today.day, calendar_module.monthrange(year, month)[1])
	return date(year, month, day)


# Returns all occurrences of (day, month) within the rolling window
# [today - 1 month, today + 1 year].
# For Feb 29, non-leap years are skipped silently.
def occurrencesInWindow(day, month):
	today = date.today()
	window_start = _windowStart()
	window_end = date(today.year + 1, today.month, today.day)
	occurrences = []
	for year in [today.year - 1, today.year, today.year + 1]:
		try:
			occurrence = date(year, month, day)
			if window_start <= occurrence <= window_end:
				occurrences.append(occurrence)
		except ValueError:
			pass  # e.g. Feb 29 in a non-leap year
	return occurrences


def getBirthdays():
	agentlist = Person.objects.filter(starred=True).exclude(day_of_birth__isnull=True).exclude(month_of_birth__isnull=True)
	birthdays = []
	for agent in agentlist.distinct():
		for occurrence_date in occurrencesInWindow(agent.day_of_birth, agent.month_of_birth):
			# Hard requirement: don't show birthdays before the year of birth
			if agent.year_of_birth and occurrence_date.year < agent.year_of_birth:
				continue
			if agent.year_of_birth:
				age = occurrence_date.year - agent.year_of_birth
				label = _('%(name)s\'s %(count)s Birthday') % {
					'name': agent.getName(),
					'count': ordinal(age)
				}
			else:
				label = _('%(name)s\'s Birthday') % {
					'name': agent.getName()
				}
			birthdays.append({
				'date': occurrence_date,
				'label': label,
				'link': agent.get_absolute_url(),
				'uid': "birthday_"+str(agent.id)+"_"+str(occurrence_date.year),
			})
	return birthdays

def getDeathdays():
	agentlist = Person.objects.filter(starred=True).exclude(day_of_death__isnull=True).exclude(month_of_death__isnull=True)
	deathdays = []
	for agent in agentlist.distinct():
		for occurrence_date in occurrencesInWindow(agent.day_of_death, agent.month_of_death):
			# Hard requirement: don't show deathdays before the year of death
			if agent.year_of_death and occurrence_date.year < agent.year_of_death:
				continue
			label = _('%(name)s\'s Deathday') % {'name': agent.getName()}
			deathdays.append({
				'date': occurrence_date,
				'label': label,
				'link': agent.get_absolute_url(),
				'uid': "deathday_"+str(agent.id)+"_"+str(occurrence_date.year),
			})
	return deathdays

def getWeddings():
	relationships = RomanticRelationship.objects.filter(active=True).filter_starred().exclude(wedding_day__isnull=True).exclude(wedding_month__isnull=True)
	weddingdays = []
	for relationship in relationships.distinct():
		for occurrence_date in occurrencesInWindow(relationship.wedding_day, relationship.wedding_month):
			if relationship.milestone == 'married':
				# Hard requirement: don't show anniversaries before the wedding year
				if relationship.wedding_year and occurrence_date.year < relationship.wedding_year:
					continue
				if relationship.wedding_year:
					age = occurrence_date.year - relationship.wedding_year
					label = _('%(names)s\'s %(count)s Anniversary') % {
						'names': relationship.getFirstNames(),
						'count': ordinal(age)
					}
				else:
					label = _('%(names)s\'s Anniversary') % {
						'names': relationship.getFirstNames()
					}
			elif relationship.milestone == 'engaged':
				# Only show in the year of the wedding itself
				if occurrence_date.year != relationship.wedding_year:
					continue
				label = _('%(names)s\'s Wedding') % {
					'names': relationship.getFirstNames()
				}
			else:
				continue
			weddingdays.append({
				'date': occurrence_date,
				'label': label,
				'link': relationship.personA.get_absolute_url(), # Hack: there's no UI for weddings yet, so link to one of the people's pages
				'uid': "wedding_"+str(relationship.id)+"_"+str(occurrence_date.year),
			})
	return weddingdays


def getEvents():
	events = getBirthdays() + getDeathdays() + getWeddings()
	events.sort(key=lambda event: event['date'])
	return events


def buildICalendar(events=None):
	"""Build and return the ICalendar bytes for all events in the rolling window.
	Accepts an optional pre-computed events list to avoid duplicate DB queries."""
	if events is None:
		events = getEvents()
	cal = Calendar()
	cal.add('prodid', '-//lucos//contacts//')
	cal.add('version', '2.0')
	for eventData in events:
		event = Event()
		event.add('uid', "lucos_contacts//"+eventData['uid'])
		event.add('summary', eventData['label'])
		event.add('dtstart', eventData['date'])
		event.add('dtstamp', datetime.now())
		cal.add_component(event)
	return cal.to_ical()


@login_required
def renderCalendar(request):
	return render(None, 'agents/index.html', {
		'template': 'agents/calendar.html',
		'title': _("Contacts Calendar"),
		'list': 'calendar',
		'addurl': reverse('admin:agents_person_add'),
		'events': getEvents(),
		'icalendar_link': '/calendar.ics?key='+get_calendar_key(),
	})

@csrf_exempt
@calendar_auth
@login_required
def outputICalendar(request):
	ical_bytes = buildICalendar()
	return HttpResponse(content=ical_bytes, content_type=f'text/calendar; charset={settings.DEFAULT_CHARSET}')
