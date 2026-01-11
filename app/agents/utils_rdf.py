import os
import rdflib
from agents.models import *
from .models.relationshipTypes import RELATIONSHIP_TYPES, getRelationshipTypeByKey
from django.conf import settings
from django.utils import translation

BASE_URL = os.environ.get("APP_ORIGIN")
CONTACTS_NS = rdflib.Namespace(BASE_URL)
EOLAS_NS = rdflib.Namespace(f"https://eolas.l42.eu/ontology/")

def agent_to_rdf(agent, include_type_label=False):
	agent_uri = CONTACTS_NS[agent.get_absolute_url()]
	g = rdflib.Graph()
	g.bind('reltypes', BASE_URL+"/relationships/")
	g.bind('eolas', EOLAS_NS)
	g.add((agent_uri, rdflib.RDF.type, rdflib.FOAF.Person))
	if include_type_label:
		g.add((rdflib.FOAF.Person, rdflib.SKOS.prefLabel, rdflib.Literal("Person", lang='en')))
		g.add((rdflib.FOAF.Person, EOLAS_NS.hasCategory, EOLAS_NS.People))
		g.add((EOLAS_NS.People, rdflib.SKOS.prefLabel, rdflib.Literal("People", lang='en')))
	g.add((agent_uri, rdflib.SKOS.prefLabel, rdflib.Literal(str(agent))))
	for agentname in PersonName.objects.filter(agent=agent):
		g.add((agent_uri, rdflib.FOAF.name, rdflib.Literal(agentname.name)))
	if agent.day_of_birth and agent.month_of_birth:
		g.add((agent_uri, rdflib.FOAF.birthday, rdflib.Literal(f"{agent.month_of_birth}-{agent.day_of_birth}")))

	for num in PhoneNumber.objects.filter(agent=agent, active=True):
		g.add((agent_uri, rdflib.FOAF.phone, rdflib.URIRef(f"tel:{num.number}")))
	for email in EmailAddress.objects.filter(agent=agent, active=True):
		g.add((agent_uri, rdflib.FOAF.mbox, rdflib.URIRef(f"mailto:{email.address}")))
	for postaladdress in PostalAddress.objects.filter(agent=agent, active=True):
		g.add((agent_uri, rdflib.SDO.address, rdflib.Literal(postaladdress.address.replace(',', ',\n'))))
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
	for relation in Relationship.objects.filter(subject=agent):
		rel_type = getRelationshipTypeByKey(relation.relationshipType)
		g.add((agent_uri, CONTACTS_NS[rel_type.get_absolute_url()], CONTACTS_NS[relation.object.get_absolute_url()]))
	return g

def agent_list_to_rdf(agentlist):
	g = rdflib.Graph()
	g.bind('reltypes', BASE_URL+"/relationships/")
	g.bind('eolas', EOLAS_NS)
	g += rel_types_rdf()
	for agent in agentlist:
		g += agent_to_rdf(agent, include_type_label=False)
	return g

def rel_types_rdf():
	g = rdflib.Graph()
	g.add((rdflib.FOAF.Person, rdflib.RDF.type, rdflib.OWL.Class))
	g.add((rdflib.FOAF.Person, rdflib.SKOS.prefLabel, rdflib.Literal("Person", lang='en')))
	g.add((rdflib.FOAF.Person, EOLAS_NS.hasCategory, EOLAS_NS.People))
	g.add((EOLAS_NS.People, rdflib.SKOS.prefLabel, rdflib.Literal("People", lang='en')))
	for reltype in RELATIONSHIP_TYPES:
		type_uri = CONTACTS_NS[reltype.get_absolute_url()]
		g.add((type_uri, rdflib.RDFS.subPropertyOf, rdflib.URIRef('https://dbpedia.org/ontology/relative')))
		for lang, _ in settings.LANGUAGES:
			with translation.override(lang):
				g.add((type_uri, rdflib.SKOS.prefLabel, rdflib.Literal(translation.gettext(reltype.label).title(), lang=lang)))
	return g
