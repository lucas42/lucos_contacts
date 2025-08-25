from django.db import models
from django import utils
from settings import AUTH_DOMAIN
from django.contrib.auth.models import AbstractBaseUser, User
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
			if os.environ.get("PRODUCTION"):
				return None
			else:
				print("Non-production environment; creating user "+str(data['id']))
				agent = Agent.objects.create(id=data['id'])
		try:
			user = LucosUser.objects.get(agent=agent)
		except LucosUser.DoesNotExist:
			print("Creating auth user for agent "+str(agent.id))
			user = LucosUser.objects.create(agent=agent)

			# HACK: Also create a django native User object with the same ID
			# So that django_admin_log doesn't error
			User.objects.create(id=user.id)
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
		if (app_label == 'comms'):
			return True
		if (app_label == 'lucosauth'):
			return True
		return False
	def has_perm(self, perm, obj=None):
		if (perm.startswith('agents.')):
			return True
		if (perm.startswith('comms.')):
			return True
		if (perm.startswith('lucosauth.')):
			return True
		return False
	def get_short_name(self):
		return self.agent.getName()
	def get_long_name(self):
		return self.agent.getName()
	def get_username(self):
		return self.agent.getName()
