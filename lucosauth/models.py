from django.db import models
from django import utils
from local_settings import AUTH_DOMAIN
from urllib2 import HTTPError
from django.contrib.auth.models import User
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
		username = 'lucos:'+data['id']
		try:
			user = User.objects.get(username=username)
		except User.DoesNotExist:
			user = User(username=username)
			user.save()
		return user

	def get_user(self, user_id):
		try:
			return User.objects.get(pk=user_id)
		except User.DoesNotExist:
			return None