import os
import rdflib
from agents.models import *

BASE_URL = os.environ.get("BASE_URL")

def agent_to_rdf(agent):
	agent_uri = rdflib.URIRef(f"{BASE_URL}{agent.get_absolute_url()}")
	g = rdflib.Graph()
	g.add((agent_uri, rdflib.RDF.type, rdflib.FOAF.Agent))
	g.add((agent_uri, rdflib.SKOS.prefLabel, rdflib.Literal(str(agent))))
	for agentname in AgentName.objects.filter(agent=agent):
		g.add((agent_uri, rdflib.FOAF.name, rdflib.Literal(agentname.name)))
	if agent.day_of_birth and agent.month_of_birth:
		g.add((agent_uri, rdflib.FOAF.birthday, rdflib.Literal(f"{agent.month_of_birth}-{agent.day_of_birth}")))

	for num in PhoneNumber.objects.filter(agent=agent, active=True):
		g.add((agent_uri, rdflib.FOAF.phone, rdflib.URIRef(f"tel:{num.number}")))
	for email in EmailAddress.objects.filter(agent=agent, active=True):
		g.add((agent_uri, rdflib.FOAF.mbox, rdflib.URIRef(f"mailto:{email.address}")))
	for facebookaccount in FacebookAccount.objects.filter(agent=agent, active=True):
		account_bnode = rdflib.BNode()
		g.add((agent_uri, rdflib.FOAF.account, account_bnode))
		g.add((account_bnode, rdflib.FOAF.accountName, rdflib.Literal(str(facebookaccount.userid))))
		g.add((account_bnode, rdflib.FOAF.accountServiceHomepage, rdflib.URIRef("https://www.facebook.com/")))
	for googleaccount in GoogleAccount.objects.filter(agent=agent, active=True):
		account_bnode = rdflib.BNode()
		g.add((agent_uri, rdflib.FOAF.account, account_bnode))
		g.add((account_bnode, rdflib.FOAF.accountName, rdflib.Literal(googleaccount.userid)))
		g.add((account_bnode, rdflib.FOAF.accountServiceHomepage, rdflib.URIRef("https://myaccount.google.com/")))
	return g

def agent_list_to_rdf(agentlist):
	g = rdflib.Graph()
	for agent in agentlist:
		g += agent_to_rdf(agent)
	return g