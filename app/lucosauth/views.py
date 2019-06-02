from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from local_settings import API_KEY, AUTH_DOMAIN
from django.http import HttpResponse, Http404
from django import utils

def loginview(request):
	user = None
	if ('token' in request.GET):
		user = authenticate(token=request.GET['token'])
	if user is None:
		return redirect('https://'+AUTH_DOMAIN+'/authenticate?' + utils.http.urlencode({'redirect_uri': request.build_absolute_uri()}))
	login(request, user)
	if (request.GET['next'].startswith('/admin/') and user.is_staff is False):
		return HttpResponse("<html><head><script type='text/javascript' src='/bootloader'></script><title>Access Denied</title></head><body>Your account doesn't have access to this page.<nav><a href='/'>&lt;- Home</a></nav></body></html>", status=403)
	if ('next' in request.GET):
		return redirect(request.GET['next'])
	return redirect('/')    
