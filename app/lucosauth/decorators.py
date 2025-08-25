from functools import wraps
from lucosauth.models import ApiUser
from lucosauth.envvars import getUserByKey
from django.http import HttpResponse

def api_auth(func):
	@wraps(func)
	def _decorator(request, *args, **kwargs):
		from django.contrib.auth import login
		if 'HTTP_AUTHORIZATION' in request.META:
			authmeth, auth = request.META['HTTP_AUTHORIZATION'].split(' ', 1)
			if authmeth.lower() == 'key':
				try:
					user = ApiUser.objects.get(apikey=auth)
					login(request, user)
				except ApiUser.DoesNotExist:
					user = getUserByKey(apikey=auth)
					if user:
						request.user = user
					else:
						return HttpResponse(status=403)
		return func(request, *args, **kwargs)
	return _decorator

def calendar_auth(func):
	@wraps(func)
	def _decorator(request, *args, **kwargs):
		from django.contrib.auth import login
		if 'key' in request.GET:
			try:
				user = ApiUser.objects.get(apikey=request.GET['key'])
				login(request, user)
			except ApiUser.DoesNotExist:
				user = getUserByKey(apikey=request.GET['key'])
				if user:
					request.user = user
				else:
					return HttpResponse(status=403)
		return func(request, *args, **kwargs)
	return _decorator