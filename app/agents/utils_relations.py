from django.utils.translation import gettext as _

def get_relationship_info(agent, currentagent):
	if not currentagent:
		return ('', -1)
	
	if agent.id == currentagent.id:
		return (_('Me'), -1)

	combinedrels = ''
	priority = -1
	
	# Relationships where currentagent is the subject (e.g. currentagent is parent of agent)
	for rel in [r for r in currentagent.subject.all() if r.object_id == agent.id]:
		combinedrels += rel.get_relationshipType_display() + "/"
		priority = rel.getPriority()
		
	# Romantic relationships
	current_person_ids = {agent.id, currentagent.id}
	for rel in [r for r in currentagent.personA.all() if r.personB_id == agent.id] + [r for r in currentagent.personB.all() if r.personA_id == agent.id]:
		if rel.active:
			combinedrels += rel.getRelationshipLabel() + "/"
			priority = rel.getPriority()

	rel_str = combinedrels.strip('/')
	return (rel_str, priority)
