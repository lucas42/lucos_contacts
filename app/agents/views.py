from agents.models import *
from lucosauth.decorators import api_auth, require_scope
from django.http import HttpResponse, Http404, HttpResponseBadRequest, JsonResponse
from django import utils
from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.urls import reverse
from django.core.exceptions import MultipleObjectsReturned
import json, time, os
from django.core.paginator import Paginator
from agents.calendar import getEvents, buildICalendar, getContactEventsToday
from agents.loganne import contactCreated, contactUpdated, contactStarChanged
from agents.serialize import serializePerson
from agents.importer import importPerson
from agents.utils_relations import get_relationship_info
from django.utils.translation import gettext as _
from .utils_conneg import negotiate_response_format
from .utils_rdf import agent_to_rdf, agent_list_to_rdf
from django.conf import settings


def _resolve_person(extid):
	"""Look up Person by external ID. Returns (ext, agent) or raises Http404.

	Raises Http404 if no ExternalPerson with that pk exists.
	Returns (ext, agent) where agent may differ from ext (canonical redirect case).
	"""
	try:
		ext = ExternalPerson.objects.get(pk=extid)
	except ExternalPerson.DoesNotExist:
		raise Http404
	return ext, ext.agent


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(api_auth, name='dispatch')
@method_decorator(require_scope('contacts:read'), name='dispatch')
class PersonDetailView(View):
	"""GET /people/{extid} — person detail (read-only, contacts:read)."""

	def get(self, request, extid):
		if extid == 'me':
			# API and machine callers have no concept of 'me'
			if request.user.agent is None:
				raise Http404
			return redirect(request.user.agent)

		ext, agent = _resolve_person(extid)
		if agent.id != ext.id:
			return redirect(agent)

		fmt, rdf_info = negotiate_response_format(request)
		if fmt == "json":
			return JsonResponse({'id': agent.id, 'name': agent.getName(), 'url': agent.get_absolute_url()})
		if fmt == "rdf":
			graph = agent_to_rdf(agent, include_type_label=True)
			rdflib_format, content_type = rdf_info
			return HttpResponse(graph.serialize(format=rdflib_format), content_type=f'{content_type}; charset={settings.DEFAULT_CHARSET}')

		output = serializePerson(agent=agent, currentagent=request.user.agent, extended=True)
		# Puts a zero width space before the at sign in emails
		# so that long email addresses get split across lines in a more sensible place.
		output['email'] = [{"view": email.replace("@", "​@"), "raw": email} for email in output['email']]
		output['title'] = output['name']
		return render(None, 'agents/agent.html', output)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(api_auth, name='dispatch')
@method_decorator(require_scope('contacts:write'), name='dispatch')
class PersonAccountsView(View):
	"""POST /people/{extid}/accounts — update account links (contacts:write)."""

	def post(self, request, extid):
		ext, agent = _resolve_person(extid)
		if agent.id != ext.id:
			return redirect(agent)

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
			except MultipleObjectsReturned:
				continue
		if agentModified:
			contactUpdated(agent)
		return HttpResponse(status=204)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(api_auth, name='dispatch')
class PersonStarredView(View):
	"""GET/PUT /people/{extid}/starred — read (contacts:read) or update (contacts:write)."""

	@method_decorator(require_scope('contacts:read'))
	def get(self, request, extid):
		ext, agent = _resolve_person(extid)
		if agent.id != ext.id:
			return redirect(agent)
		return HttpResponse(content=str(agent.starred))

	@method_decorator(require_scope('contacts:write'))
	def put(self, request, extid):
		ext, agent = _resolve_person(extid)
		if agent.id != ext.id:
			return redirect(agent)
		agent.starred = (request.body.decode('utf-8').lower() == "true")
		agent.save()
		contactStarChanged(agent)
		return HttpResponse(content=str(agent.starred))
	

@csrf_exempt
@api_auth
@require_scope('contacts:write')
@require_http_methods(["POST"])
def importer(request):
	data = json.loads(request.body)
	output = importPerson(data)
	return JsonResponse(output)

PAGE_SIZE = 50
PAGINATED_LISTS = {'all', 'phone'}

@api_auth
@require_scope('contacts:read')
def agentindex(request, list):
	agents = []
	template = 'agents/agentlist.html'
	prefetches = ['personname_set']
	if (list == 'postal'):
		agentlist = Person.objects.filter(postaladdress__isnull=False)
		prefetches.append('postaladdress_set')
	elif (list == 'phone'):
		prefetches.append('phonenumber_set')
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

	agentlist = agentlist.prefetch_related(*prefetches)

	fmt, rdf_info = negotiate_response_format(request)
	if fmt == "json":
		people = [
			{'id': agent.id, 'name': agent.getName(), 'url': agent.get_absolute_url()}
			for agent in agentlist.distinct()
		]
		return JsonResponse(people, safe=False)
	if fmt == "rdf":
		graph = agent_list_to_rdf(agentlist)
		rdflib_format, content_type = rdf_info
		return HttpResponse(graph.serialize(format=rdflib_format), content_type=f'{content_type}; charset={settings.DEFAULT_CHARSET}')

	current_agent = request.user.agent
	if current_agent:
		models.prefetch_related_objects([current_agent], 'subject', 'personA', 'personB')

	for agent in agentlist.distinct():
		data = {
			'id': agent.id,
			'name': agent.getName(),
			'names': [p.name for p in agent.personname_set.all()],
			'url': agent.get_absolute_url(),
			'starred': agent.starred,
			'isDead': agent.is_dead,
		}

		if (list == 'postal'):
			active_addresses = [p for p in agent.postaladdress_set.all() if p.active]
			if not active_addresses:
				continue
			data['formattedaddresses'] = [p.address.replace(',', ',\n') for p in active_addresses]
		elif (list == 'phone'):
			active_phones = [p for p in agent.phonenumber_set.all() if p.active]
			if not active_phones:
				continue
			data['phone'] = [str(p.number).replace('+44','0') for p in active_phones]
		elif (list == 'gifts'):
			data['giftideas'] = agent.gift_ideas

		data['rel'], data['sortableRel'] = get_relationship_info(agent, current_agent)
		agents.append(data)
	if list in PAGINATED_LISTS:
		paginator = Paginator(agents, PAGE_SIZE)
		page_obj = paginator.get_page(request.GET.get('page', 1))
		agents_page = page_obj.object_list
	else:
		page_obj = None
		agents_page = agents

	return render(None, 'agents/index.html', {
		'template': template,
		'title': _("Contacts"),
		'agents': agents_page,
		'list': list,
		'addurl': reverse('admin:agents_person_add'),
		'page_obj': page_obj,
	})

@api_auth
@require_scope('contacts:read')
def events_today(request):
	events = getContactEventsToday()
	return JsonResponse(events, safe=False)


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
			},
			'calendar-event-count': {
				'techDetail': "Number of events in the generated ICS file",
			},
			'calendar-file-size-bytes': {
				'techDetail': "Size of the generated ICS file in bytes",
			},
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
	try:
		calendar_events = getEvents()
		ical_bytes = buildICalendar(calendar_events)
		output['metrics']['calendar-event-count']['value'] = len(calendar_events)
		output['metrics']['calendar-file-size-bytes']['value'] = len(ical_bytes)
	except Exception as e:
		output['metrics']['calendar-event-count']['value'] = -1
		output['metrics']['calendar-event-count']['debug'] = str(e)
		output['metrics']['calendar-file-size-bytes']['value'] = -1
		output['metrics']['calendar-file-size-bytes']['debug'] = str(e)
	return HttpResponse(content=json.dumps(output), content_type=f'application/json; charset={settings.DEFAULT_CHARSET}')

def manifest(request):
	output = {
		'name': "lucOS Contacts",
		'short_name': "Contacts",
		'start_url': "/people/starred",
		'scope': "/",
		'theme_color': "#000000",
		'background_color': "#DBFFE6",
		'display': "standalone",
		'icons': [
			{
				"sizes": "434x425",
				"src": "/resources/logo-highres.png",
				"type": "image/png",
				"purpose": "any monochrome",
			},
			{
				"sizes": "510x510",
				"src": "/resources/maskable_icon.png",
				"type": "image/png",
				"purpose": "maskable",
			}
		]
		}
	return HttpResponse(content=json.dumps(output), content_type=f'application/manifest+json; charset={settings.DEFAULT_CHARSET}')
