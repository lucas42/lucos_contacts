from django.db import models
from django.contrib.auth.models import AbstractBaseUser
from agents.models import Person

class LucosUser(AbstractBaseUser):
	agent = models.OneToOneField(Person, on_delete=models.CASCADE)
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
