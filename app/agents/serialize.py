from agents.models import *
import datetime
from django.urls import reverse
from django.utils.translation import gettext as _
from agents.utils_relations import get_relationship_info


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

def serializePerson(agent, currentagent=None, extended=False):

	phonenums = []
	for num in [p for p in agent.phonenumber_set.all() if p.active]:
		phonenums.append(str(num.number)
			.replace('+44','0') # Display UK numbers as local.  TODO: don't hardcode this
		)
	rawaddresses = []
	formattedaddresses = []
	for postaladdress in [p for p in agent.postaladdress_set.all() if p.active]:
		rawaddresses.append(postaladdress.address)
		formattedaddresses.append(postaladdress.address.replace(',', ',\n'))
	emailaddresses = [email.address for email in agent.emailaddress_set.all() if email.active]
	facebookaccounts = [facebookaccount.userid for facebookaccount in agent.facebookaccount_set.all() if facebookaccount.active]
	googlecontacts = [googlecontact.contactid for googlecontact in agent.googlecontact_set.all() if googlecontact.active]
	googlephotoprofiles = [profile.search_path for profile in agent.googlephotosprofile_set.all() if profile.active]

	altnames = []
	for agentname in [p for p in agent.personname_set.all() if not p.is_primary]:
		altnames.append(agentname.name)

	formattedBirthday = formatDate(agent.year_of_birth, agent.month_of_birth, agent.day_of_birth)
	sortableBirthday = sortableDate(agent.year_of_birth, agent.month_of_birth, agent.day_of_birth)
	formattedDeathDate = formatDate(agent.year_of_death, agent.month_of_death, agent.day_of_death)

	agentdataobj = {
		'id': agent.id,
		'name': agent.getName(),
		'altnames': altnames,
		'phone': phonenums,
		'email': emailaddresses,
		'url': agent.get_absolute_url(),
		'addresses': rawaddresses,
		'formattedaddresses': formattedaddresses,
		'facebookaccounts': facebookaccounts,
		'googlecontacts': googlecontacts,
		'googlephotoprofiles': googlephotoprofiles,
		'editurl': reverse('admin:agents_person_change', args=(agent.id,)),
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
		for relation in agent.subject.all():
			agentdataobj['relations'].append(serializePerson(agent=relation.object, currentagent=agent, extended=False))
		for relationship in [p for p in agent.personA.all() if p.active] + [p for p in agent.personB.all() if p.active]:
			partner = relationship.getOtherPerson(agent)
			agentdataobj['relations'].append(serializePerson(agent=partner, currentagent=agent, extended=False))
		agentdataobj['relations'].sort(key=lambda data: (data['sortableRel'], data['sortableBirthday']))

	agentdataobj['rel'], agentdataobj['sortableRel'] = get_relationship_info(agent, currentagent)

	return agentdataobj