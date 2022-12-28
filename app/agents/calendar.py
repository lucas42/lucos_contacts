from django.shortcuts import render
from agents.models import *
from django.urls import reverse
from datetime import date
from django.utils.translation import gettext as _
from django.contrib.humanize.templatetags.humanize import ordinal

def getBirthdays():
	agentlist = Agent.objects.filter(starred=True).exclude(day_of_birth__isnull=True).exclude(month_of_birth__isnull=True)
	birthdays = []
	for agent in agentlist.distinct():
		if agent.year_of_birth:
			currentYear = date.today().year
			age = currentYear - agent.year_of_birth
			if nextYear(agent.day_of_birth, agent.month_of_birth):
				age += 1
			label = _('%(name)s\'s %(count)s Birthday') % {
				'name': agent.getName(),
				'count': ordinal(age)
			}
		else:
			label = _(
				'%(name)s\'s Birthday'
			) % {
				'name': agent.getName()
			}
		birthdays.append({
			'day': agent.day_of_birth,
			'month': agent.month_of_birth,
			'label': label,
			'agent': agent,
			'link': agent.get_absolute_url(),
		})
	return birthdays

def getDeathdays():
	agentlist = Agent.objects.filter(starred=True).exclude(day_of_death__isnull=True).exclude(month_of_death__isnull=True)
	deathdays = []
	for agent in agentlist.distinct():
		label = _('%(name)s\'s Deathday') % {'name': agent.getName()}
		deathdays.append({
			'day': agent.day_of_death,
			'month': agent.month_of_death,
			'label': label,
			'agent': agent,
			'link': agent.get_absolute_url(),
		})
	return deathdays

def getDates():
	dates = getBirthdays() + getDeathdays()
	dates.sort(key=lambda date: (nextYear(date['day'], date['month']), date['month'], date['day']))
	return dates

# Returns boolean.
# True if the next instance of this date is next year.
# False if there's a remaining this year (including today).
def nextYear(day, month):
	currentDay = date.today().day
	currentMonth = date.today().month
	if month > currentMonth:
		return False
	if month < currentMonth:
		return True
	return (day < currentDay)

def renderCalendar(request):
	return render(None, 'agents/index.html', {
		'template': 'agents/calendar.html',
		'list': 'calendar',
		'addurl': reverse('admin:agents_agent_add'),
		'dates': getDates(),
	})