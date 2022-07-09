# -*- coding: utf-8 -*-
from django.db import models
from django.utils import translation
from django.core.exceptions import ObjectDoesNotExist
from agents.relationshipTypes import RELATIONSHIP_TYPE_CHOICES, getRelationshipTypeByKey
import datetime

def getCurrentLang():
	cur_language = translation.get_language()
	if cur_language is None:
		return ""
	return cur_language[:2]

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

class BaseAccount(models.Model):
	agent = models.ForeignKey(Agent, blank=False, on_delete=models.CASCADE)
	active = models.BooleanField(default=True)
	class Meta:
		abstract = True
	@staticmethod
	def getByParams(params):
		accountTypes = {
			"facebook": FacebookAccount,
			"google": GoogleAccount,
			"phone": PhoneNumber,
			"email": EmailAddress,
			"googlecontact": GoogleContact,

			# HACK:Technically not an account, but also has an `.agent` relationship, so works for now
			"name": AgentName,
		}
		accountArgs = params.dict()
		typeid = accountArgs.pop("type")
		accountType = accountTypes.get(typeid)
		if accountType is None:
			raise ObjectDoesNotExist("Can't find account of type "+typeid)
		return accountType.objects.get(**accountArgs)

class PhoneNumber(BaseAccount):
	number = models.CharField(max_length=127, blank=False)
	def __str__(self):
		if getCurrentLang() == 'ga':
			return 'Uimhir guathan '+self.agent.getName()
		return self.agent.getName()+"'s Phone Number"

class EmailAddress(BaseAccount):
	address = models.EmailField(max_length=255, blank=False)
	class Meta:
		verbose_name_plural = "Email Addresses"
	def __str__(self):
		if getCurrentLang() == 'ga':
			return u'Seolodh Ríomhphost '+self.agent.getName()
		return self.agent.getName()+"'s Email Address"

class PostalAddress(BaseAccount):
	address = models.CharField(max_length=255, blank=False)
	class Meta:
		verbose_name_plural = "Postal Addresses"
	def __str__(self):
		if getCurrentLang() == 'ga':
			return 'Seoladh '+self.agent.getName()
		return self.agent.getName()+"'s Address"

class FacebookAccount(BaseAccount):
	userid = models.PositiveBigIntegerField(blank=False)
	username = models.CharField(max_length=255, blank=True)
	def __str__(self):
		if getCurrentLang() == 'ga':
			return 'Cuntas Facebook '+self.agent.getName()
		return self.agent.getName()+"'s Facebook Account"

# An actual google acount, which can be logged into by the user
class GoogleAccount(BaseAccount):
	userid = models.CharField(max_length=255, blank=False)
	def __str__(self):
		if getCurrentLang() == 'ga':
			return 'Cuntas Google '+self.agent.getName()
		return self.agent.getName()+"'s Google Account"

# A contact from Google Contacts
class GoogleContact(BaseAccount):
	contactid = models.CharField(max_length=127, blank=False)
	def __str__(self):
		if getCurrentLang() == 'ga':
			return u'Teagmháil Google '+self.agent.getName()
		return self.agent.getName()+"'s Google Contact"

class Relationship(models.Model):
	subject = models.ForeignKey(Agent, related_name='subject', blank=False, on_delete=models.CASCADE)
	object = models.ForeignKey(Agent, related_name='object', blank=False, on_delete=models.CASCADE)
	relationshipType = models.CharField(choices=RELATIONSHIP_TYPE_CHOICES, blank=False, max_length=127)
	def save(self, *args, **kwargs):
		super(Relationship, self).save(*args, **kwargs)
		self.inferRelationships()

	def inferRelationships(self):
		relationshipType = getRelationshipTypeByKey(self.relationshipType)
		if relationshipType.transitive:
			others = Relationship.objects.filter(subject=self.object, relationshipType=relationshipType.dbKey).exclude(object=self.subject)
			for item in others:
				Relationship.objects.get_or_create(subject=self.subject, object=item.object, relationshipType=relationshipType.dbKey)
			others = Relationship.objects.filter(object=self.subject, relationshipType=relationshipType.dbKey).exclude(subject=self.object)
			for item in others:
				Relationship.objects.get_or_create(subject=item.subject, object=self.object, relationshipType=relationshipType.dbKey)
		if relationshipType.inverse:
			Relationship.objects.get_or_create(subject=self.object, object=self.subject, relationshipType=relationshipType.inverse.dbKey)
		for connection in relationshipType.outgoingRels:
			for existingRel in Relationship.objects.filter(subject=self.object, relationshipType=connection.existingRel.dbKey):
				Relationship.objects.get_or_create(subject=self.subject, object=existingRel.object, relationshipType=connection.inferredRel.dbKey)
		for connection in relationshipType.incomingRels:
			for existingRel in Relationship.objects.filter(object=self.subject, relationshipType=connection.existingRel.dbKey):
				Relationship.objects.get_or_create(subject=existingRel.subject, object=self.object, relationshipType=connection.inferredRel.dbKey)

	def getPriority(self):
		for index, choice in enumerate(RELATIONSHIP_TYPE_CHOICES):
			if choice[0] == self.relationshipType:
				return index
		return -1

	def __str__(self):
		return self.subject.getName()+" - "+self.get_relationshipType_display()+" - "+self.object.getName()
