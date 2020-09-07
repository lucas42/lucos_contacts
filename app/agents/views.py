from agents.models import *
from lucosauth.decorators import api_auth
from django.http import HttpResponse, Http404
from django import utils
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.core.exceptions import MultipleObjectsReturned
import json, time, os

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
			newagent = Agent(name_en=request.POST.get('name_en', ""), name_ga=request.POST.get('name_ga', ""), name_gd=request.POST.get('name_gd', ""), name_cy=request.POST.get('name_cy', ""))
			newagent.save()
			return redirect(newagent)
		else:
			template = 'agent-add.html'
			output = {}
			output.update(csrf(request))
			return render(None, 'agents/'+template, output)
	try:
		ext = ExternalAgent.objects.get(pk=extid)
		agent = ext.agent
	except ExternalAgent.DoesNotExist:
		raise Http404
	if (agent.id != ext.id):
		return redirect(agent)
	
	output = agentdata(agent, request.user.agent, True)
	if (method == 'accounts'):
		if (request.method == 'POST'):
			accountlist = json.loads(request.body)
			for accountData in accountlist:
				accountTypes = {
					"facebook": FacebookAccount,
					"google": GoogleAccount,
					"phone": PhoneNumber,
					"email": EmailAddress,
					"googlecontact": GoogleContact,
				}
				typeid = accountData.pop("type")
				accountType = accountTypes.get(typeid)
				if accountType is None:
					return HttpResponse(status=404, content="Unknown account type \""+typeid+"\"\n")
				try:
					account = accountType.objects.get(agent=agent, **accountData)
				except ObjectDoesNotExist:
					account = accountType(agent=agent, **accountData)
				account.save()
		return HttpResponse(status=204)
	else:
		template = 'agent.html'
	return render(None, 'agents/'+template, output)
	
	
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
	return render(None, 'agents/index.html', {
		'template': template,
		'agents': agents,
		'list': list,
		'addurl': reverse('admin:agents_agent_add'),
	})

# Get a bunch of data abount an agent
# agent: the Agent in to get info about
# currentagent: The Agent that relationships should be relative to
# extended: whether to get information about relatives
def agentdata(agent, currentagent, extended=False):

	phonenums = []
	for num in PhoneNumber.objects.filter(agent=agent, active=True):
			phonenums.append(num.number)
	rawaddresses = []
	formattedaddresses = []
	for postaladdress in PostalAddress.objects.filter(agent=agent, active=True):
			rawaddresses.append(postaladdress.address)
			formattedaddresses.append(postaladdress.address.replace(',', ',\n'))
	facebookaccounts = []
	for facebookaccount in FacebookAccount.objects.filter(agent=agent, active=True):
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
		'editurl': reverse('admin:agents_agent_change', args=(agent.id,)),
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
				agentdataobj['rel'] = rel.relationshipType
	except Relationship.DoesNotExist:
		pass

	return agentdataobj

def identify(request):
	try:
		account = BaseAccount.getByParams(request.GET)
	except ObjectDoesNotExist as e:
		return HttpResponse(status=404, content=str(e)+"\n")
	except MultipleObjectsReturned as e:
		return HttpResponse(status=409, content=str(e)+"\n")
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
		}
	}
	try:
		ext = ExternalAgent.objects.get(pk=1)
		output['checks']['db']['ok'] = True
	except Exception as e:
		output['checks']['db']['ok'] = False
		output['checks']['db']['debug'] = str(e)
	try:
		[output['metrics']['agent-count']['value']] = len(Agent.objects.all()),
	except Exception as e:
		output['metrics']['agent-count']['value'] = -1
		output['metrics']['agent-count']['debug'] = str(e)
	return HttpResponse(content=json.dumps(output))
