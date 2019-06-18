# -*- coding: utf-8 -*-
from django.db import models
from django.utils import translation
from django.core.exceptions import ObjectDoesNotExist

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

	def __unicode__(self):
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
	agent = models.ForeignKey(Agent, blank=False)
	def __unicode__(self):
		return self.agent.getName()

class AccountType(models.Model):
	label_en = models.CharField(max_length=255, blank=True)
	label_ga = models.CharField(max_length=255, blank=True)
	label_gd = models.CharField(max_length=255, blank=True)
	label_cy = models.CharField(max_length=255, blank=True)
	accounturi = models.CharField(max_length=255, blank=True)
	
	def getLabel(self):
		return getTranslated(self, 'label')

	def __unicode__(self):
		return self.getLabel()

class BaseAccount(models.Model):
	agent = models.ForeignKey(Agent, blank=False)
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
	
class Account(BaseAccount):
	type = models.ForeignKey(AccountType, blank=False)
	domain = models.CharField(max_length=255, blank=True, help_text='')
	userid = models.CharField(max_length=255, blank=True, help_text='Must be unique for the given type in the given domain.  Usually persistant')
	username = models.CharField(max_length=255, blank=True, help_text='Usually unique for the given type/domain.  Can change over time.')
	url = models.CharField(max_length=255, blank=True)
	name = models.CharField(max_length=255, blank=True, help_text='Not guaranteed to be unique.')
	imgurl = models.CharField(max_length=255, blank=True)
	
	def __unicode__(self):
		if getCurrentLang() == 'ga':
			return 'Cuntas '+self.type.getLabel()+' '+self.agent.getName()
		return self.agent.getName()+"'s "+self.type.getLabel()+" account"

class PhoneNumber(BaseAccount):
	number = models.CharField(max_length=127, blank=False)
	def __unicode__(self):
		if getCurrentLang() == 'ga':
			return 'Uimhir guathan '+self.agent.getName()
		return self.agent.getName()+"'s Phone Number"

class EmailAddress(BaseAccount):
	address = models.EmailField(max_length=255, blank=False)
	class Meta:
		verbose_name_plural = "Email Addresses"
	def __unicode__(self):
		if getCurrentLang() == 'ga':
			return u'Seolodh Ríomhphost '+self.agent.getName()
		return self.agent.getName()+"'s Email Address"

class PostalAddress(BaseAccount):
	address = models.CharField(max_length=255, blank=False)
	class Meta:
		verbose_name_plural = "Postal Addresses"
	def __unicode__(self):
		if getCurrentLang() == 'ga':
			return 'Seoladh '+self.agent.getName()
		return self.agent.getName()+"'s Address"

class FacebookAccount(BaseAccount):
	userid = models.PositiveIntegerField(blank=False)
	username = models.CharField(max_length=255, blank=True)
	def __unicode__(self):
		if getCurrentLang() == 'ga':
			return 'Cuntas Facebook '+self.agent.getName()
		return self.agent.getName()+"'s Facebook Account"

# An actual google acount, which can be logged into by the user
class GoogleAccount(BaseAccount):
	userid = models.CharField(max_length=255, blank=False)
	def __unicode__(self):
		if getCurrentLang() == 'ga':
			return 'Cuntas Google '+self.agent.getName()
		return self.agent.getName()+"'s Google Account"

# A contact from Google Contacts
class GoogleContact(BaseAccount):
	contactid = models.CharField(max_length=127, blank=False)
	def __unicode__(self):
		if getCurrentLang() == 'ga':
			return u'Teagmháil Google '+self.agent.getName()
		return self.agent.getName()+"'s Google Contact"

class RelationshipType(models.Model):
	label_en = models.CharField(max_length=255, blank=True)
	label_ga = models.CharField(max_length=255, blank=True)
	label_gd = models.CharField(max_length=255, blank=True)
	label_cy = models.CharField(max_length=255, blank=True)
	symmetrical = models.BooleanField(default=False)
	transitive = models.BooleanField(default=False)
	inverse = models.OneToOneField('self', null=True, blank=True)
	
	
	def save(self, *args, **kwargs):
		if self.symmetrical:
			self.inverse = self
		self.symmetrical = self.inverse == self
		if self.inverse and self.inverse.inverse != self:
			#print "inverse:"+self.inverse.__unicode__();
			self.inverse.inverse = self
			self.inverse.save()
			#print "inverseinverse:"+self.inverse.inverse.__unicode__();
		super(RelationshipType, self).save(*args, **kwargs)
		self.inferRelationships()
	
	def getLabel(self):
		return getTranslated(self, 'label')

	# Infer Relationships for all relationships of this type
	def inferRelationships(self):
		for relationship in Relationship.objects.filter(type=self):
			relationship.inferRelationships()

	def __unicode__(self):
		return self.getLabel()

class Relationship(models.Model):
	subject = models.ForeignKey(Agent, related_name='subject', blank=False)
	object = models.ForeignKey(Agent, related_name='object', blank=False)
	type = models.ForeignKey(RelationshipType, blank=False, help_text='Subject is a $type of object')
	def save(self, *args, **kwargs):
		super(Relationship, self).save(*args, **kwargs)
		self.inferRelationships()

	def inferRelationships(self):
		#print "--Saved "+self.__unicode__()
		# Set inferred relationships
		if self.type.transitive:
			#print "\ttransitive"
			others = Relationship.objects.filter(subject=self.object, type=self.type).exclude(object=self.subject)
			for item in others:
				if self.subject == item.object:
					continue
				try:
					Relationship.objects.get(subject=self.subject, object=item.object, type=self.type)
				except Relationship.DoesNotExist:
					Relationship.objects.create(subject=self.subject, object=item.object, type=self.type)
			others = Relationship.objects.filter(object=self.subject, type=self.type).exclude(object=self.object)
			for item in others:
				if item.subject == self.object:
					continue
				try:
					Relationship.objects.get(subject=item.subject, object=self.object, type=self.type)
				except Relationship.DoesNotExist:
					Relationship.objects.create(subject=item.subject, object=self.object, type=self.type)
				#print "\t\t\t"+Relationship.objects.get(subject=self.subject, object=item.object, type=self.type).__unicode__()
		if self.type.inverse:
			#print "\tinverse"
			try:
				Relationship.objects.get(subject=self.object, object=self.subject, type=self.type.inverse)
			except Relationship.DoesNotExist:
				Relationship.objects.create(subject=self.object, object=self.subject, type=self.type.inverse)
			#print "\t\t\t"+Relationship.objects.get(subject=self.object, object=self.subject, type=self.type.inverse).__unicode__()
				
		for connection in RelationshipTypeConnection.objects.filter(inferred_relation_type=self.type, reversible=True).exclude(relation_type_b=None):
			#print "\tConnection(infer): "+connection.__unicode__()
			for relationship_a in Relationship.objects.filter(subject=self.subject, type=connection.relation_type_a):
				#print "\t\texistingrel(a):"+relationship_a.__unicode__()
				try:
					Relationship.objects.get(subject=relationship_a.object, object=self.object, type=connection.relation_type_b)
				except Relationship.DoesNotExist:
					Relationship.objects.create(subject=relationship_a.object, object=self.object, type=connection.relation_type_b)
				#print "\t\t\t"+Relationship.objects.get(subject=relationship_a.object, object=self.object, type=connection.relation_type_b).__unicode__()
			for relationship_b in Relationship.objects.filter(object=self.object, type=connection.relation_type_b):
				#print "\t\texistingrel(b):"+relationship_b.__unicode__()
				try:
					Relationship.objects.get(subject=self.subject, object=relationship_b.subject, type=connection.relation_type_a)
				except Relationship.DoesNotExist:
					Relationship.objects.create(subject=self.subject, object=relationship_b.subject, type=connection.relation_type_a)
				#print "\t\t\t"+Relationship.objects.get().__unicode__()
			
		for connection in RelationshipTypeConnection.objects.filter(relation_type_a=self.type).exclude(relation_type_b=None):
			#print "\tConnection(a): "+connection.__unicode__()
			#print "\tSelf.subject: "+self.subject.__unicode__()
			for relationship_b in Relationship.objects.filter(object=self.subject, type=connection.relation_type_b):
				#print "\trelationship_b.object: "+relationship_b.object.__unicode__()
				#print "\t\texistingrel(b):"+relationship_b.__unicode__()
				try:
					Relationship.objects.get(subject=relationship_b.subject, object=self.object, type=connection.inferred_relation_type)
				except Relationship.DoesNotExist:
					Relationship.objects.create(subject=relationship_b.subject, object=self.object, type=connection.inferred_relation_type)
				#print "\t\t\t"+Relationship.objects.get(subject=relationship_b.subject, object=self.object, type=connection.inferred_relation_type).__unicode__()
						
		for connection in RelationshipTypeConnection.objects.filter(relation_type_b=self.type):
			#print "\tConnection(b): "+connection.__unicode__()
			for relationship_a in Relationship.objects.filter(subject=self.object, type=connection.relation_type_a):
				#print "\t\texistingrel(a):"+relationship_a.__unicode__()
				try:
					Relationship.objects.get(subject=self.subject, object=relationship_a.object, type=connection.inferred_relation_type)
				except Relationship.DoesNotExist:
					Relationship.objects.create(subject=self.subject, object=relationship_a.object, type=connection.inferred_relation_type)
				#print "\t\t\t"+Relationship.objects.get(subject=self.subject, object=relationship_a.object, type=connection.inferred_relation_type).__unicode__()
		#print "--Done "+self.__unicode__()
			
	def __unicode__(self):
		return self.subject.getName()+" - "+self.type.getLabel()+" - "+self.object.getName()

class RelationshipTypeConnection(models.Model):
	relation_type_a = models.ForeignKey(RelationshipType, related_name='a', blank=False)
	relation_type_b = models.ForeignKey(RelationshipType, related_name='b', blank=True, null=True)
	inferred_relation_type = models.ForeignKey(RelationshipType, related_name='inferred', blank=False)
	reversible = models.BooleanField(default=False)
	def __unicode__(self):
		return "a="+self.relation_type_a.getLabel()+" b="+self.relation_type_b.getLabel()+" infer="+self.inferred_relation_type.getLabel()


	def save(self, *args, **kwargs):
		super(RelationshipTypeConnection, self).save(*args, **kwargs)

		# Find any existing relationships which may be affected by this new connection
		self.relation_type_a.inferRelationships()
		self.relation_type_b.inferRelationships()
		if self.reversible:
			self.inferred_relation_type.inferRelationships()
