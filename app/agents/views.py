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
	elif (method == 'starred'):
		if (request.method == 'PUT'):
			agent.starred = (request.body.decode('utf-8').lower() == "true")
			agent.save()
		return HttpResponse(content=str(agent.starred))
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
	elif (list == 'starred'):
		agentlist = Agent.objects.filter(starred=True)
	elif (list == 'all'):
		agentlist = Agent.objects.all()
	else:
		agentlist = Agent.objects.filter(id=0)
	for agent in agentlist.distinct().order_by('id'):
		data = agentdata(agent, request.user.agent)

		# Hide any agents who only have inactive postal addresses
		# (the above filter only excludes agents with no postal addresses at all)
		if (list == 'postal' and not data['addresses']):
			continue
		agents.append(data)
	return render(None, 'agents/index.html', {
		'template': template,
		'agents': agents,
		'list': list,
		'addurl': reverse('admin:agents_agent_add'),
	})

# Formats a date given the year, month of day - any selection of which may be missing
def formatDate(year, month, day):
	monthname = None
	if month:
		monthname = datetime.date(1970, month, 1).strftime('%B')
	if (day and month and year):
		return str(day)+"/"+str(month)+"/"+str(year)
	elif (monthname and year):
		return str(monthname)+" "+str(year)
	elif (year):
		return str(year)
	elif (day and month):
		return str(day)+"/"+str(month)
	elif (monthname):
		return "Sometime in "+str(monthname)
	elif (day):
		return str(day)+" of something"
	else:
		return None

# Returns a string which can be used in a .sort() function given a year, month and day
def sortableDate(year, month, day):
	if (year is None):
		year = 9999
	if (month is None):
		month = 13
	if (day is None):
		day = 32
	return str(year).zfill(4)+'-'+str(month).zfill(2)+'-'+str(day).zfill(2)


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

	altnames = []
	for agentname in AgentName.objects.filter(agent=agent, is_primary=False):
		altnames.append(agentname.name)

	formattedBirthday = formatDate(agent.year_of_birth, agent.month_of_birth, agent.day_of_birth)
	sortableBirthday = sortableDate(agent.year_of_birth, agent.month_of_birth, agent.day_of_birth)
	formattedDeathDate = formatDate(agent.year_of_death, agent.month_of_death, agent.day_of_death)

	agentdataobj = {
		'agent': agent,
		'name': agent.getName(),
		'altnames': altnames,
		'phone': phonenums,
		'url': agent.get_absolute_url(),
		'addresses': rawaddresses,
		'formattedaddresses': formattedaddresses,
		'facebookaccounts': facebookaccounts,
		'editurl': reverse('admin:agents_agent_change', args=(agent.id,)),
		'bio': agent.bio,
		'notes': agent.notes,
		'giftideas': agent.gift_ideas,
		'formattedBirthday': formattedBirthday,
		'sortableBirthday': sortableBirthday,
		'formattedDeathDate': formattedDeathDate,
		'isDead': agent.is_dead,
		'starred': agent.starred,
	}

	if extended:
		agentdataobj['relations'] = []
		for relation in Relationship.objects.filter(subject=agent):
			agentdataobj['relations'].append(agentdata(relation.object, agent))
		agentdataobj['relations'].sort(key=lambda data: (data['sortableRel'], data['sortableBirthday']))

	if currentagent:
		agentdataobj['sortableRel'] = -1
		if (agent == currentagent):
			agentdataobj['rel'] = 'me'
		else:
			combinedrels = ''
			for rel in Relationship.objects.filter(object=agent.id, subject=currentagent.id):
				combinedrels += rel.get_relationshipType_display() + "/"
				agentdataobj['sortableRel'] = rel.getPriority()
			agentdataobj['rel'] = combinedrels.strip('/')

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
		},
		'icon': "/resources/logo-highres.png",
		'network_only': True,
		'title': "Contacts",
		'show_on_homepage': True
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
