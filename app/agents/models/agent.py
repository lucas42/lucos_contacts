# -*- coding: utf-8 -*-
from django.db import models
from django.db.models.functions import Lower
import datetime

def dayChoices():
	choices = []
	for day in range(1,32):
		choices.append((day, day))
	return choices

def monthChoices():
	choices = []
	for month in range(1,13):
		choices.append((month, datetime.date(1970, month, 1).strftime('%B')))
	return choices


class Agent(models.Model):
	_name = models.CharField(max_length=255, blank=True, editable=False) #denormalised field - automatically updated by AgentName when is_primary
	starred = models.BooleanField(default=False)
	relation = models.ManyToManyField('self', through='Relationship', symmetrical=False)
	day_of_birth = models.IntegerField(choices=dayChoices(), blank=True, null=True)
	month_of_birth = models.IntegerField(choices=monthChoices(), blank=True, null=True)
	year_of_birth = models.IntegerField(blank=True, null=True)
	day_of_death = models.IntegerField(choices=dayChoices(), blank=True, null=True)
	month_of_death = models.IntegerField(choices=monthChoices(), blank=True, null=True)
	year_of_death = models.IntegerField(blank=True, null=True)
	is_dead = models.BooleanField(default=False)
	bio = models.TextField(blank=True)
	notes = models.TextField(blank=True)
	on_gift_list = models.BooleanField(default=False)
	gift_ideas = models.TextField(blank=True)

	class Meta:
		app_label = 'agents'
		ordering = [Lower('_name')]

	def getName(self):
		return self._name or "Unnamed"

	def __str__(self):
		return self.getName()
		
	def save(self, *args, **kwargs):
		# If there's any details about their death, it's reasonable to assume the person is dead
		if self.year_of_death is not None or self.month_of_death is not None or self.day_of_death is not None:
			self.is_dead = True

		super(Agent, self).save(*args, **kwargs)
		try:
			ext = ExternalAgent.objects.get(id=self.id)
			ext.agent = self
		except ExternalAgent.DoesNotExist:
			ext = ExternalAgent.objects.create(id=self.id, agent=self)
			
	def get_absolute_url(self):
		return "/agents/%i" % self.id

	
class ExternalAgent(models.Model):
	agent = models.ForeignKey(Agent, blank=False, on_delete=models.CASCADE)
	def __str__(self):
		return self.agent.getName()

class AgentName(models.Model):
	agent = models.ForeignKey(Agent, blank=False, on_delete=models.CASCADE)
	name = models.CharField(max_length=255, blank=False)
	is_primary = models.BooleanField(default=False)
	def save(self, *args, **kwargs):

		# If this agent has no primary name, make this the primary
		primaryCount = AgentName.objects.filter(agent=self.agent, is_primary=True).count()
		if primaryCount == 0:
			self.is_primary = True

		#  If this is the primary name, ensure none of the other names for that agent are primary any more
		if self.is_primary:
			queryset = AgentName.objects.filter(agent=self.agent)
			if self.pk:
				queryset = queryset.exclude(pk=self.pk)
			queryset.update(is_primary=False)
			self.agent._name = self.name
			self.agent.save()
		super(AgentName, self).save(*args, **kwargs)
	def __str__(self):
		return self.name