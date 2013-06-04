from agents.models import Agent, ExternalAgent, AccountType, Account, RelationshipType, Relationship, RelationshipTypeConnection
from django.http import HttpResponse, Http404
from django import utils
from django.shortcuts import redirect, render_to_response
from django.core.context_processors import csrf
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from local_settings import API_KEY
import json, time, urllib2, os

# Returns a HttpResponse object
# If auth has been successful the status will be 204, and the wrapper function can do it's own thing
# Any other response should be returned to the client
@csrf_exempt
def authenticate(request):
	
	@csrf_protect
	def needs_csrf_protection(request):
		return HttpResponse(status=204)
		
	if ('agentid' in request.session and request.session['agentid']):
		try:
			agent = ExternalAgent.objects.get(pk=request.session['agentid']).agent
		except ExternalAgent.DoesNotExist:
			return HttpResponse(status=403)
		
		# Only end user requests require CSRF protection
		response = needs_csrf_protection(request)
		response.agent = agent
		return response
	if ('HTTP_AUTHORIZATION' in request.META):
		
		# TODO: support multiple keys
		if (request.META['HTTP_AUTHORIZATION'] == "Key "+API_KEY):
			request.session['agentid'] = None
			return HttpResponse(status=204)
		else:
			return HttpResponse(status=403)
	if ('token' in request.GET):
		data = json.load(urllib2.urlopen('http://auth.l42.eu/data?' + utils.http.urlencode({'token': request.GET['token']})))
		if (data['id'] == None):
			return HttpResponse(status=500)
		request.session['agentid'] = data['id']
		return redirect(request.path)
	return redirect('http://auth.l42.eu/authenticate?' + utils.http.urlencode({'redirect_uri': request.build_absolute_uri()}))

@csrf_exempt
def agent(request, extid, method):
	auth = authenticate(request)
	if (auth.status_code != 204):
		return auth
	if (extid == 'me'):
		# API requests have no concept of 'me'
		if (auth.agent == None):
			raise Http404
		return redirect(auth.agent)
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
	
	output = agentdata(agent, request.session['agentid'])
	if (method == 'edit'):
		template = 'agent-edit.html'
		if (request.method == 'POST'):
			new_numbers = filter(None, request.POST.getlist('telnum'))
			to_delete = array_diff(phonenums, new_numbers)
			to_add = array_diff(new_numbers, phonenums)
			for i, v in enumerate(to_delete):
				Account.objects.filter(type=phonenumbertype).filter(agent=agent).filter(userid=v).delete()
			for i, v in enumerate(to_add):
				num = Account(type=phonenumbertype, agent=agent, userid=v)
				num.save()
			output['phone'] = new_numbers

			new_addresses = filter(None, request.POST.getlist('addresses'))
			to_delete = array_diff(rawaddresses, new_addresses)
			to_add = array_diff(new_addresses, rawaddresses)
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
	
def agentindex(request, list):
	auth = authenticate(request)
	if (auth.status_code != 204):
		return auth
	agents = []
	if (list == 'postal'):
		addresstype = AccountType(id=10)
		agentlist = Agent.objects.filter(account__type=addresstype)
	elif (list == 'phone'):
		phonenumbertype = AccountType(id=5)
		agentlist = Agent.objects.filter(account__type=phonenumbertype)
	elif (list == 'all'):
		agentlist = Agent.objects.all()
	else:
		agentlist = Agent.objects.filter(id=0)
	for agent in agentlist.distinct():
		agents.append(agentdata(agent, request.session['agentid']))
	return render_to_response('agents/index.html', {'agents': agents, 'list': list })

def agentdata(agent, currentid):

	phonenums = []
        phonenumbertype = AccountType(id=5)
        for num in Account.objects.filter(type=phonenumbertype).filter(agent=agent):
                phonenums.append(num.userid)
        rawaddresses = []
        formattedaddresses = []
        addresstype = AccountType(id=10)
        for address in Account.objects.filter(type=addresstype).filter(agent=agent):
                rawaddresses.append(address.url)
                formattedaddresses.append(address.url.replace(',', ',\n'))
	
	agentdata = {'agent': agent, 'name': agent.getName(), 'phone': phonenums, 'url': agent.get_absolute_url(), 'isme': agent.id == currentid, 'addresses': rawaddresses, 'formattedaddresses': formattedaddresses}
        try:
                rel = Relationship.objects.get(subject=agent.id, object=currentid)
                agentdata['rel'] = rel.type.getLabel()
        except Relationship.DoesNotExist:
                if (agent.id == currentid):
                        agentdata['rel'] = 'me'
	return agentdata

def identify(request):
	try:
		type = AccountType.objects.get(id=request.GET.get('type', ''))
		if (request.GET.get('domain', False)):
			account = Account.objects.get(type=type, domain=request.GET.get('domain', ''), userid=request.GET.get('id', ''))
		else:
			account = Account.objects.get(type=type, userid=request.GET.get('id', ''))
	except AccountType.DoesNotExist:
		raise Http404
	except Account.DoesNotExist:
		raise Http404
	return redirect(account.agent)
	
def resources(request):
	resourcefiles = {
		'_lucos': { 'filename': "../core/lucos.js", 'type': 'js'},
		'contacts': { 'filename': "templates/resources/script.js", 'type': 'js'},
		'style': { 'filename': "templates/resources/style.css", 'type': 'css'}
	};
	output = {}
	resources = {}
	version = 0
	for key, val in resourcefiles.iteritems():
		filename = val['filename']
		if (os.path.getmtime(filename) > version):
			version = os.path.getmtime(filename)
		file = open(filename)
		text = ''
		for line in file:
			text += line
		output[key] = text
		resources[key] = val['type']
	output['r'] = resources
	output['v'] = version
	return HttpResponse(json.dumps(output), 'application/json')
