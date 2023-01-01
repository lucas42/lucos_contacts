# -*- coding: utf-8 -*-
from django.db import models
from .relationshipTypes import RELATIONSHIP_TYPE_CHOICES, getRelationshipTypeByKey
from .agent import Agent
from django.db.models.functions import Lower

class Relationship(models.Model):
	subject = models.ForeignKey(Agent, related_name='subject', blank=False, on_delete=models.CASCADE)
	object = models.ForeignKey(Agent, related_name='object', blank=False, on_delete=models.CASCADE)
	relationshipType = models.CharField(choices=RELATIONSHIP_TYPE_CHOICES, blank=False, max_length=127)
	class Meta:
		# Ideally this would just be ['subject'], and then follow the Lower('_name') bit on the agent model
		# However, the `Lower` function seems to cause that to error in quite a cryptic way
		# So easiest fix is just be more explicit here
		# Note the the first two underscores are for separating the the model from the field; the third underscore is part of the field name.
		ordering = [Lower('subject___name')]
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
