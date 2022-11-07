# -*- coding: utf-8 -*-
from agents.models import *
from django.core.exceptions import BadRequest, MultipleObjectsReturned, ObjectDoesNotExist
from django.db.models.fields import NOT_PROVIDED
from agents.loganne import contactUpdated, contactCreated

## Imports data regarding a particular individual
def importAgent(data):
	validate(data)
	output = {}
	agent = identify(data['identifiers'])
	output['existing'] = bool(agent)
	if not agent:
		agent = Agent.objects.create()
	output['id'] = agent.id
	output['updated'] = update(agent, data['identifiers'])

	# Only call loganne once per agent, regardless of how many creations/updates there were
	# TODO: work out how to check calls to loganne in unit tests
	if not output['existing']:
		contactCreated(agent)
	elif output['updated']:
		contactUpdated(agent)
	return output

## Checks the data given is in a valid format
## Throws a BadRequest exception if the data isn't valid
def validate(data):
	if 'identifiers' not in data:
		raise BadRequest("Key 'identifiers' missing")
	if not isinstance(data['identifiers'], list):
		raise BadRequest("Key 'identifiers' isn't an array")
	for identifier in data["identifiers"]:
		if 'type' not in identifier:
			raise BadRequest("Identifier missing 'type'")
		try:
			accountType = BaseAccount.getTypeByKey(identifier["type"])
		except (ObjectDoesNotExist, TypeError):
			raise BadRequest(f"Unknown identifier type '{identifier['type']}'")
		validFields = [field.name for field in accountType._meta.get_fields()]
		for field in identifier:
			if field == "type":
				continue
			if field not in validFields:
				raise BadRequest(f"Unknown field '{field}'")

## Gets the fields which are used when comparing for identify
## Returns a dict of key/value pairs
def get_identification_fields(identifier):
	accountType = BaseAccount.getTypeByKey(identifier["type"])
	identification_fields = {}
	for field in accountType._meta.get_fields():
		if field.name is not "agent" and not field.blank and field.default is NOT_PROVIDED:
			identification_fields[field.name] = identifier[field.name]
	return identification_fields

## Gets the fields used for creating or updating an Account (Should be a superset of the idientification_fields)
## Returns a dict of key/value pairs
def get_update_fields(identifier):
	accountType = BaseAccount.getTypeByKey(identifier["type"])
	update_fields = {}
	for field in accountType._meta.get_fields():
		if field.name in identifier:
			update_fields[field.name] = identifier[field.name]
	return update_fields

## Given a list of identifier dicts, attempts to ascertain which agent is referred to
## Returns an agent if one is found, otherwise None
def identify(identifiers):
	for identifier in identifiers:
		accountType = BaseAccount.getTypeByKey(identifier["type"])
		try:
			account = accountType.objects.get(**get_identification_fields(identifier))
			return account.agent
		except (ObjectDoesNotExist, MultipleObjectsReturned):
			# If there's not exactly one agent which matches this identifer, then ignore it and go on to the next
			continue
	return None

## Updates a given agent with a list of identifiers
## Returns a boolean of whether any changes were made
def update(agent, identifiers):
	updated = False
	for identifier in identifiers:
		accountType = BaseAccount.getTypeByKey(identifier["type"])
		try:
			account = accountType.objects.get(agent=agent, **get_identification_fields(identifier))
			for key, value in get_update_fields(identifier).items():
				if getattr(account, key, None) != value:
					setattr(account, key, value)
					account.save()
					updated = True
			continue
		except ObjectDoesNotExist:
			accountType.objects.create(agent=agent, **get_update_fields(identifier))
			updated = True
		except MultipleObjectsReturned:
			# Ideally one agent shouldn't have two identical accounts, but not much can be done about it at this point
			continue
	return updated