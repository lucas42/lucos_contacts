# -*- coding: utf-8 -*-
from django.db import models
from django.utils import translation
from django.core.exceptions import ObjectDoesNotExist
from agents.relationshipTypes import RELATIONSHIP_TYPE_CHOICES, getRelationshipTypeByKey
from django.urls import reverse
from phonenumber_field.modelfields import PhoneNumberField
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


# Formats a date given the year, month of day - any selection of which may be missing
def formatDate(year, month, day):
	monthname = None
	if month:
		monthname = datetime.date(1970, month, 1).strftime('%B')
	if (day and month and year):
		return str(day)+"/"+str(month)+"/"+str(year)
	elif (monthname and year):
		return str(monthname)+" "+str(year)
	elif (year):
		return str(year)
	elif (day and month):
		return str(day)+"/"+str(month)
	elif (monthname):
		return "Sometime in "+str(monthname)
	elif (day):
		return str(day)+" of something"
	else:
		return None

# Returns a string which can be used in a .sort() function given a year, month and day
def sortableDate(year, month, day):
	if (year is None):
		year = 9999
	if (month is None):
		month = 13
	if (day is None):
		day = 32
	return str(year).zfill(4)+'-'+str(month).zfill(2)+'-'+str(day).zfill(2)

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

	def getData(self, currentagent=None, extended=False):

		phonenums = []
		for num in PhoneNumber.objects.filter(agent=self, active=True):
				phonenums.append(str(num.number)
					.replace('+44','0') # Display UK numbers as local.  TODO: don't hardcode this
				)
		rawaddresses = []
		formattedaddresses = []
		for postaladdress in PostalAddress.objects.filter(agent=self, active=True):
				rawaddresses.append(postaladdress.address)
				formattedaddresses.append(postaladdress.address.replace(',', ',\n'))
		facebookaccounts = []
		for facebookaccount in FacebookAccount.objects.filter(agent=self, active=True):
				facebookaccounts.append(facebookaccount.userid)

		altnames = []
		for agentname in AgentName.objects.filter(agent=self, is_primary=False):
			altnames.append(agentname.name)

		formattedBirthday = formatDate(self.year_of_birth, self.month_of_birth, self.day_of_birth)
		sortableBirthday = sortableDate(self.year_of_birth, self.month_of_birth, self.day_of_birth)
		formattedDeathDate = formatDate(self.year_of_death, self.month_of_death, self.day_of_death)

		agentdataobj = {
			'id': self.id,
			'name': self.getName(),
			'altnames': altnames,
			'phone': phonenums,
			'url': self.get_absolute_url(),
			'addresses': rawaddresses,
			'formattedaddresses': formattedaddresses,
			'facebookaccounts': facebookaccounts,
			'editurl': reverse('admin:agents_agent_change', args=(self.id,)),
			'bio': self.bio,
			'notes': self.notes,
			'giftideas': self.gift_ideas,
			'formattedBirthday': formattedBirthday,
			'sortableBirthday': sortableBirthday,
			'formattedDeathDate': formattedDeathDate,
			'isDead': self.is_dead,
			'starred': self.starred,
		}

		if extended:
			agentdataobj['relations'] = []
			for relation in Relationship.objects.filter(subject=self):
				agentdataobj['relations'].append(relation.object.getData(currentagent=self, extended=False))
			agentdataobj['relations'].sort(key=lambda data: (data['sortableRel'], data['sortableBirthday']))

		if currentagent:
			agentdataobj['sortableRel'] = -1
			if (self == currentagent):
				agentdataobj['rel'] = 'me'
			else:
				combinedrels = ''
				for rel in Relationship.objects.filter(object=self.id, subject=currentagent.id):
					combinedrels += rel.get_relationshipType_display() + "/"
					agentdataobj['sortableRel'] = rel.getPriority()
				agentdataobj['rel'] = combinedrels.strip('/')

		return agentdataobj
	
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
	number = PhoneNumberField(blank=False)
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
