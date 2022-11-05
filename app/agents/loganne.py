import requests
from agents.serialize import serializeAgent

def loganneRequest(data):
	data["source"] = "lucos_contacts"
	loganne_reponse = requests.post('https://loganne.l42.eu/events', json=data);
	if loganne_reponse.status_code != 202:
		print ("Error from Loganne: " + loganne_reponse.text)

def agentAction(agent, action):
	loganneRequest({
		"type": "contact"+action.title(),
		"humanReadable": "Contact \""+agent.getName()+"\" "+action,
		"agent": serializeAgent(agent=agent),
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