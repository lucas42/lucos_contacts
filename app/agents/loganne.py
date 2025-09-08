import requests
from os import environ
from agents.serialize import serializePerson

def loganneRequest(data):
	data["source"] = "lucos_contacts"
	if not environ.get("LOGANNE_ENDPOINT"):
		return
	try:
		loganne_reponse = requests.post(environ.get("LOGANNE_ENDPOINT"), json=data);
		loganne_reponse.raise_for_status()
	except Exception as error:
		print("Error from Loganne: {}".format(error))

def agentAction(agent, action):
	loganneRequest({
		"type": "contact"+action.title(),
		"humanReadable": "Contact \""+agent.getName()+"\" "+action,
		"agent": serializePerson(agent=agent),
		"url": "https://contacts.l42.eu" + agent.get_absolute_url(),
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

def contactDeleted(agent_name, agent_id):
	loganneRequest({
		"type": "contactDeleted",
		"humanReadable": "Contact \""+agent_name+"\" deleted",
		"agent": {
			"id": agent_id,
			"name": agent_name,
		}
	})