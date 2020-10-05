# -*- coding: utf-8 -*-
from django.db import models
from django.utils import translation
from django.core.exceptions import ObjectDoesNotExist
from agents.relationshipTypes import RELATIONSHIP_TYPE_CHOICES, getRelationshipTypeByKey

def getCurrentLang():
	cur_language = translation.get_language()
	if cur_language is None:
		return ""
	return cur_language[:2]

def getTranslated(obj, field):
	val = getattr(obj, field+'_'+getCurrentLang(), None)
	if val:
		return val
	langs = ['en', 'ga', 'gd', 'cy']
	for ii in langs:	
		val = getattr(obj, field+'_'+ii, None)
		if val:
			return val
	return "unknown"

class Agent(models.Model):
	name_en = models.CharField(max_length=255, blank=True)
	name_ga = models.CharField(max_length=255, blank=True)
	name_gd = models.CharField(max_length=255, blank=True)
	name_cy = models.CharField(max_length=255, blank=True)
	starred = models.BooleanField(default=False)
	relation = models.ManyToManyField('self', through='Relationship', symmetrical=False)
	bio = models.TextField(blank=True)
	notes = models.TextField(blank=True)
	on_gift_list = models.BooleanField(default=False)
	gift_ideas = models.TextField(blank=True)
	def getName(self):
		return getTranslated(self, 'name')

	def __str__(self):
		return self.getName()
		
	def save(self, *args, **kwargs):
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
	userid = models.PositiveIntegerField(blank=False)
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
			
	def __str__(self):
		return self.subject.getName()+" - "+self.get_relationshipType_display()+" - "+self.object.getName()
