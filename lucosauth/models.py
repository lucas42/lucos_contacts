from django.db import models
from django import utils
from local_settings import AUTH_DOMAIN
from urllib2 import HTTPError
from django.contrib.auth.models import AbstractBaseUser
from agents.models import Agent
import json, time, urllib2, os

class LucosAuthBackend(object):
	def authenticate(self, token):
		url = 'http://'+AUTH_DOMAIN+'/data?' + utils.http.urlencode({'token': token})
		try:
			data = json.load(urllib2.urlopen(url))
		except HTTPError:
			return None
		if (data['id'] == None):
			print "No id returned by auth service; "+url
			return None
		try:
			agent = Agent.objects.get(id=data['id'])
		except Agent.DoesNotExist:
			print "Unknown id returned by auth service; "+url
			return None
		try:
			user = LucosUser.objects.get(agent=agent)
		except LucosUser.DoesNotExist:
			user = LucosUser(agent=agent)
			user.save()
		return user

	def get_user(self, user_id):
		try:
			user = LucosUser.objects.get(pk=user_id)
			return user
		except LucosUser.DoesNotExist:
			return None

class LucosUser(AbstractBaseUser):
	agent = models.OneToOneField(Agent)
	def is_staff(self):
		return self.agent.id == 2
	def has_module_perms(self, app_label):
		if (app_label == 'agents'):
			return True
		return False
	def has_perm(self, perm, obj=None):
		if (perm.startswith('agents.')):
			return True
		return False
	def get_short_name(self):
		return self.agent.getName()
	def get_long_name(self):
		return self.agent.getName()