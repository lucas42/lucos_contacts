import requests
from os import environ
from agents.serialize import serializePerson

BASE_URL = environ.get("APP_ORIGIN")

def loganneRequest(data):
	data["source"] = "lucos_contacts"
	if not environ.get("LOGANNE_ENDPOINT"):
		return
	try:
		loganne_reponse = requests.post(environ.get("LOGANNE_ENDPOINT"), json=data, headers={"User-Agent": environ.get("SYSTEM")});
		loganne_reponse.raise_for_status()
	except Exception as error:
		print("Error from Loganne: {}".format(error))

def agentAction(agent, action):
	loganneRequest({
		"type": "contact"+action.title(),
		"humanReadable": "Contact \""+agent.getName()+"\" "+action,
		"agent": serializePerson(agent=agent),
		"url": BASE_URL + agent.get_absolute_url(),
	})

def contactUpdated(agent):
	agentAction(agent, "updated")

def contactCreated(agent):
	agentAction(agent, "created")

def contactStarChanged(agent):
	if agent.starred:
		agentAction(agent, "starred")
	else:
		agentAction(agent, "unstarred")

def contactDeleted(agent_name, agent_id, url):
	loganneRequest({
		"type": "contactDeleted",
		"humanReadable": "Contact \""+agent_name+"\" deleted",
		"agent": {
			"id": agent_id,
			"name": agent_name,
		},
		"url": BASE_URL + url,
	})

def contactLinked(agent, previous_eolas_uri):
	loganneRequest({
		"type": "contactLinked",
		"humanReadable": "Linked contact \""+agent.getName()+"\" to eolas entity "+str(agent.eolas_uri),
		"url": BASE_URL + agent.get_absolute_url(),
		"contactUri": BASE_URL + agent.get_absolute_url(),
		"eolasUri": agent.eolas_uri,
		"previousEolasUri": previous_eolas_uri,
	})

def contactUnlinked(agent, previous_eolas_uri):
	loganneRequest({
		"type": "contactUnlinked",
		"humanReadable": "Unlinked contact \""+agent.getName()+"\" from eolas entity "+str(previous_eolas_uri),
		"url": BASE_URL + agent.get_absolute_url(),
		"contactUri": BASE_URL + agent.get_absolute_url(),
		"previousEolasUri": previous_eolas_uri,
	})

def relationshipDeleted(subject_name, object_name, rel_type_display):
	loganneRequest({
		"type": "relationshipDeleted",
		"humanReadable": f'Relationship "{rel_type_display}" between "{subject_name}" and "{object_name}" deleted',
	})
