from agents.models import *
from lucosauth.decorators import api_auth
from django.http import HttpResponse, Http404, HttpResponseBadRequest, JsonResponse
from django import utils
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.urls import reverse
from django.core.exceptions import MultipleObjectsReturned
import json, time, os
from agents.loganne import contactCreated, contactUpdated, contactStarChanged
from agents.serialize import serializePerson
from agents.importer import importPerson
from django.utils.translation import gettext as _
from .utils_conneg import choose_rdf_over_html, pick_best_rdf_format
from .utils_rdf import agent_to_rdf, agent_list_to_rdf

@csrf_exempt
@api_auth
@login_required
def agent(request, extid, method=None):
	if (extid == 'me'):
		# API requests have no concept of 'me'
		if (request.user.agent == None):
			raise Http404
		return redirect(request.user.agent)
	if (extid == 'add'):
		if (request.method == 'POST'):
			name = request.POST.get('name')
			if not name:
				return HttpResponseBadRequest("No name provided")
			newagent = Person()
			newagent.save()
			nameObject = PersonName(name=name, agent=newagent)
			nameObject.save()
			contactCreated(newagent)
			return redirect(newagent)
	try:
		ext = ExternalPerson.objects.get(pk=extid)
		agent = ext.agent
	except ExternalPerson.DoesNotExist:
		raise Http404
	if (agent.id != ext.id):
		return redirect(agent)
	
	if choose_rdf_over_html(request):
		graph = agent_to_rdf(agent)
		format, content_type = pick_best_rdf_format(request)
		return HttpResponse(graph.serialize(format=format), content_type=content_type)
	output = serializePerson(agent=agent, currentagent=request.user.agent, extended=True)
	if (method == 'accounts'):
		if (request.method == 'POST'):
			accountlist = json.loads(request.body)
			agentModified = False
			for accountData in accountlist:
				try:
					(_, created) = BaseAccount.get_or_create(agent=agent, **accountData)
					if created:
						agentModified = True
				except ObjectDoesNotExist as e:
					return HttpResponse(status=400, content=e.args[0]+"\n")
				# Treat Multiple Account Objects like one already existed
				except MultipleObjectsReturned as e:
					continue
			if agentModified:
				contactUpdated(agent)
		return HttpResponse(status=204)
	elif (method == 'starred'):
		if (request.method == 'PUT'):
			agent.starred = (request.body.decode('utf-8').lower() == "true")
			agent.save()
			contactStarChanged(agent)
		return HttpResponse(content=str(agent.starred))
	else:
		template = 'agent.html'

		# Puts a zero width space before the at sign in emails
		# So that long email addresses get split across lines in a more sensible place
		output['email'] = [{"view": email.replace("@","​@"), "raw": email} for email in output['email']]

		# Set the page title to the agent's name
		output['title'] = output['name']
	return render(None, 'agents/'+template, output)
	

@csrf_exempt
@api_auth
@login_required
@require_http_methods(["POST"])
def importer(request):
	data = json.loads(request.body)
	output = importPerson(data)
	return JsonResponse(output)

@api_auth
@login_required
def agentindex(request, list):
	agents = []
	template = 'agents/agentlist.html'
	if (list == 'postal'):
		agentlist = Person.objects.filter(postaladdress__isnull=False)
	elif (list == 'phone'):
		agentlist = Person.objects.filter(phonenumber__isnull=False)
	elif (list == 'gifts'):
		agentlist = Person.objects.exclude(gift_ideas="")
		template = 'agents/agenttable.html'
	elif (list == 'starred'):
		agentlist = Person.objects.filter(starred=True)
	elif (list == 'all'):
		agentlist = Person.objects.all()
	else:
		agentlist = Person.objects.filter(id=0)
	if choose_rdf_over_html(request):
		graph = agent_list_to_rdf(agentlist)
		format, content_type = pick_best_rdf_format(request)
		return HttpResponse(graph.serialize(format=format), content_type=content_type)
	for agent in agentlist.distinct():
		data = serializePerson(agent=agent, currentagent=request.user.agent)

		# Hide any agents who only have inactive postal addresses
		# (the above filter only excludes agents with no postal addresses at all)
		if (list == 'postal' and not data['addresses']):
			continue
		# Same for phone numbers
		if (list == 'phone' and not data['phone']):
			continue
		agents.append(data)
	return render(None, 'agents/index.html', {
		'template': template,
		'title': _("Contacts"),
		'agents': agents,
		'list': list,
		'addurl': reverse('admin:agents_person_add'),
	})

def identify(request):
	try:
		account = BaseAccount.get(**request.GET.dict())
	except ObjectDoesNotExist as e:
		return HttpResponse(status=404, content=e.args[0]+"\n")
	except MultipleObjectsReturned as e:
		return HttpResponse(status=409, content=e.args[0]+"\n")
	return redirect(account.agent)

def info(request):
	output = {
		'system': "lucos_contacts",
		'checks': {
			'db': {
				'techDetail': "Looks up test user in database",
			},
		},
		'metrics': {
			'agent-count': {
				'techDetail': "Counts the number of agents in the database",
			}
		},
		'ci': {
			'circle': "gh/lucas42/lucos_contacts",
		},
		'icon': "/resources/logo-highres.png",
		'network_only': True,
		'title': "Contacts",
		'show_on_homepage': True
	}
	try:
		ext = ExternalPerson.objects.get(pk=1)
		output['checks']['db']['ok'] = True
	except Exception as e:
		output['checks']['db']['ok'] = False
		output['checks']['db']['debug'] = str(e)
	try:
		[output['metrics']['agent-count']['value']] = len(Person.objects.all()),
	except Exception as e:
		output['metrics']['agent-count']['value'] = -1
		output['metrics']['agent-count']['debug'] = str(e)
	return HttpResponse(content=json.dumps(output))
