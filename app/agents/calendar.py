from django.shortcuts import render
from agents.models import *
from django.urls import reverse
from datetime import date

def getBirthdays():
	agentlist = Agent.objects.filter(starred=True).exclude(day_of_birth__isnull=True).exclude(month_of_birth__isnull=True)
	birthdays = []
	for agent in agentlist.distinct():
		birthdays.append({
			'day': agent.day_of_birth,
			'month': agent.month_of_birth,
			'label': agent.getName()+"'s Birthday",
			'agent': agent,
			'link': agent.get_absolute_url(),
		})
	return birthdays

def getDeathdays():
	agentlist = Agent.objects.filter(starred=True).exclude(day_of_death__isnull=True).exclude(month_of_death__isnull=True)
	deathdays = []
	for agent in agentlist.distinct():
		deathdays.append({
			'day': agent.day_of_death,
			'month': agent.month_of_death,
			'label': agent.getName()+"'s Deathday",
			'agent': agent,
			'link': agent.get_absolute_url(),
		})
	return deathdays

def getDates():
	dates = getBirthdays() + getDeathdays()
	dates.sort(key=lambda date: (not laterInYear(date['day'], date['month']), date['month'], date['day']))
	return dates

def laterInYear(day, month):
	currentDay = date.today().day
	currentMonth = date.today().month
	if month > currentMonth:
		return True
	if month < currentMonth:
		return False
	return (day >= currentDay)

def renderCalendar(request):
	return render(None, 'agents/index.html', {
		'template': 'agents/calendar.html',
		'list': 'calendar',
		'addurl': reverse('admin:agents_agent_add'),
		'dates': getDates(),
	})