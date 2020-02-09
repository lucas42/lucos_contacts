from django.db import models
from django import utils
from settings import AUTH_DOMAIN
from django.contrib.auth.models import AbstractBaseUser
from agents.models import Agent
import json, time, urllib.request, urllib.error, os

class LucosAuthBackend(object):
	def authenticate(self, request, token):
		print("LucosAuthBackend token:"+str(token))
		url = 'https://'+AUTH_DOMAIN+'/data?' + utils.http.urlencode({'token': token})
		try:
			data = json.load(urllib.request.urlopen(url, timeout=5))
		except urllib.error.HTTPError:
			return None
		except urllib.error.URLError as e:
			print("Error fetching data from auth service: "+e.message+" "+url)
			return None
		if (data['id'] == None):
			print("No id returned by auth service; "+url)
			return None
		try:
			agent = Agent.objects.get(id=data['id'])
		except Agent.DoesNotExist:
			print("Unknown id ("+str(data['id'])+") returned by auth service; "+url)
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
	agent = models.OneToOneField(Agent, on_delete=models.CASCADE)
	def is_staff(self):
		return self.agent.id == 2
	def has_module_perms(self, app_label):
		if (app_label == 'agents'):
			return True
		if (app_label == 'lucosauth'):
			return True
		return False
	def has_perm(self, perm, obj=None):
		if (perm.startswith('agents.')):
			return True
		if (perm.startswith('lucosauth.')):
			return True
		return False
	def get_short_name(self):
		return self.agent.getName()
	def get_long_name(self):
		return self.agent.getName()

class ApiUser(AbstractBaseUser):
	username = None
	agent = None
	system = models.CharField(max_length=128, blank=False, unique=True)
	apikey = models.CharField(max_length=128, blank=False, unique=True)
	USERNAME_FIELD = 'system'
	REQUIRED_FIELDS = []
	def is_staff(self):
		return False
	def has_module_perms(self, app_label):
		if (app_label == 'agents'):
			return True
		return False
	def has_perm(self, perm, obj=None):
		if (perm.startswith('agents.')):
			return True
		return False
	def get_short_name(self):
		return self.system
	def get_long_name(self):
		return self.system