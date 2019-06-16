from agents.models import *
from lucosauth.decorators import api_auth
from django.http import HttpResponse, Http404
from django import utils
from django.shortcuts import redirect, render_to_response
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.contrib.auth.decorators import login_required
from django.core import urlresolvers
import json, time, urllib2, os

@csrf_exempt
@api_auth
@login_required
def agent(request, extid, method):
	if (extid == 'me'):
		# API requests have no concept of 'me'
		if (request.user.agent == None):
			raise Http404
		return redirect(request.user.agent)
	if (extid == 'add'):
		if (request.method == 'POST'):
			newagent = Agent(name_en=request.POST.get('name_en', ""), name_ga=request.POST.get('name_ga', ""), name_gd=request.POST.get('name_gd', ""), name_cy=request.POST.get('name_cy', ""))
			newagent.save()
			return redirect(newagent)
		else:
			template = 'agent-add.html'
			output = {}
			output.update(csrf(request))
			return render_to_response('agents/'+template, output)
	try:
		ext = ExternalAgent.objects.get(pk=extid)
		agent = ext.agent
	except ExternalAgent.DoesNotExist:
		raise Http404
	if (agent.id <> ext.id):
		return redirect(agent)
	
	output = agentdata(agent, request.user.agent, True)
	if (method == 'edit'):
		template = 'agent-edit.html'
		if (request.method == 'POST'):
			new_numbers = filter(None, request.POST.getlist('telnum'))
			to_delete = array_diff(output['phone'], new_numbers)
			to_add = array_diff(new_numbers, output['phone'])
			phonenumbertype = AccountType(id=5)
			for i, v in enumerate(to_delete):
				Account.objects.filter(type=phonenumbertype).filter(agent=agent).filter(userid=v).delete()
			for i, v in enumerate(to_add):
				num = Account(type=phonenumbertype, agent=agent, userid=v)
				num.save()
			output['phone'] = new_numbers

			new_addresses = filter(None, request.POST.getlist('addresses'))
			to_delete = array_diff(output['addresses'], new_addresses)
			to_add = array_diff(new_addresses, output['addresses'])
			addresstype = AccountType(id=10)
			for i, v in enumerate(to_delete):
				Account.objects.filter(type=addresstype).filter(agent=agent).filter(url=v).delete()
			for i, v in enumerate(to_add):
				address = Account(type=addresstype, agent=agent, url=v)
				address.save()
			output['addresses'] = new_addresses

		output.update(csrf(request))
	elif (method == 'accounts'):
		
		# TODO: handle domains
		if (request.method == 'POST'):
			types = request.POST.getlist('type')
			ids = request.POST.getlist('id')
			for t, i in zip(types, ids):
				try:
					accounttype = AccountType.objects.get(id=t)
					account = Account.objects.get(type=accounttype, userid=i, agent=agent)
				except AccountType.DoesNotExist:
					raise Http404
				except Account.DoesNotExist:
					account = Account(type=accounttype, userid=i, agent=agent)
				account.save()
		return HttpResponse(status=204)
	else:
		template = 'agent.html'
	return render_to_response('agents/'+template, output)
	
	
def array_diff(a, b):
	b = set(b)
	return [aa for aa in a if aa not in b]
	

@login_required
def agentindex(request, list):
	agents = []
	template = 'agents/agentlist.html'
	if (list == 'postal'):
		agentlist = Agent.objects.filter(postaladdress__isnull=False)
	elif (list == 'phone'):
		agentlist = Agent.objects.filter(phonenumber__isnull=False)
	elif (list == 'gifts'):
		agentlist = Agent.objects.filter(on_gift_list=True)
		template = 'agents/agenttable.html'
	elif (list == 'all'):
		agentlist = Agent.objects.all()
	else:
		agentlist = Agent.objects.filter(id=0)
	for agent in agentlist.distinct().order_by('id'):
		agents.append(agentdata(agent, request.user.agent))
	return render_to_response('agents/index.html', {
		'template': template,
		'agents': agents,
		'list': list,
		'addurl': urlresolvers.reverse('admin:agents_agent_add'),
	})

# Get a bunch of data abount an agent
# agent: the Agent in to get info about
# currentagent: The Agent that relationships should be relative to
# extended: whether to get information about relatives
def agentdata(agent, currentagent, extended=False):

	phonenums = []
	for num in PhoneNumber.objects.filter(agent=agent):
			phonenums.append(num.number)
	rawaddresses = []
	formattedaddresses = []
	for postaladdress in PostalAddress.objects.filter(agent=agent):
			rawaddresses.append(postaladdress.address)
			formattedaddresses.append(postaladdress.address.replace(',', ',\n'))
	facebookaccounts = []
	for facebookaccount in FacebookAccount.objects.filter(agent=agent):
			facebookaccounts.append(facebookaccount.userid)
	
	agentdataobj = {
		'agent': agent,
		'name': agent.getName(),
		'phone': phonenums,
		'url': agent.get_absolute_url(),
		'isme': agent == currentagent,
		'addresses': rawaddresses,
		'formattedaddresses': formattedaddresses,
		'facebookaccounts': facebookaccounts,
		'editurl': urlresolvers.reverse('admin:agents_agent_change', args=(agent.id,)),
		'bio': agent.bio,
		'notes': agent.notes,
		'giftideas': agent.gift_ideas,
	}

	if extended:
		agentdataobj['relations'] = []
		for relation in Relationship.objects.filter(object=agent).order_by('subject'):
			agentdataobj['relations'].append(agentdata(relation.subject, agent))

	try:
		if currentagent:
			if (agent == currentagent):
				agentdataobj['rel'] = 'me'
			else:
				rel = Relationship.objects.get(subject=agent.id, object=currentagent.id)
				agentdataobj['rel'] = rel.type.getLabel()
	except Relationship.DoesNotExist:
		pass

	return agentdataobj

def identify(request):
	try:
		typeid = request.GET.get('type', '')
		if (typeid == "phone"):
			account = PhoneNumber.objects.get(number=request.GET.get('number', ''))
		else:
			type = AccountType.objects.get(id=typeid)
			if (request.GET.get('domain', False)):
				account = Account.objects.get(type=type, domain=request.GET.get('domain', ''), userid=request.GET.get('id', ''))
			else:
				account = Account.objects.get(type=type, userid=request.GET.get('id', ''))
	except AccountType.DoesNotExist:
		raise Http404
	except Account.DoesNotExist:
		raise Http404
	return redirect(account.agent)

