class RelationshipConnection:
	def __init__(self, existingRel, inferredRel):
		self.existingRel = existingRel
		self.inferredRel = inferredRel

class BaseRelationshipType:
	inverse = None
	dbKey = 'missing'
	transitive = False
	incomingRels = []
	outgoingRels = []
	def __init__(self, subject, object):
		self.subject = subject
		self.object = object

def setInverse(typeA, typeB):
	if typeA.inverse or typeB.inverse:
		raise Exception("Inverse already set")
	typeA.inverse = typeB
	typeB.inverse = typeA

def setSymmetrical(relType):
	if relType.inverse:
		raise Exception("Inverse already set")
	relType.inverse = relType

def setInference(rel1, rel2, inferred):
	if len(rel1.outgoingRels) == 0:
		# To avoid adding objectRels to BaseRelationshipType, create a new empty list
		rel1.outgoingRels = []
	rel1.outgoingRels.append(
		RelationshipConnection(
			existingRel = rel2,
			inferredRel = inferred
		)
	)
	if len(rel2.incomingRels) == 0:
		# To avoid adding objectRels to BaseRelationshipType, create a new empty list
		rel2.incomingRels = []
	rel2.incomingRels.append(
		RelationshipConnection(
			existingRel = rel1,
			inferredRel = inferred
		)
	)

class Child(BaseRelationshipType):
	dbKey='child'

class Parent(BaseRelationshipType):
	dbKey='parent'

setInverse(Parent, Child)

# Applies only to full siblings (ie both parents are the same)
# See HalfSibling for relationships where only one parent is shared
class Sibling(BaseRelationshipType):
	dbKey='sibling'
	transitive=True
class HalfSibling(BaseRelationshipType):
	dbKey='half-sibling'

setSymmetrical(Sibling)
setSymmetrical(HalfSibling)

setInference(Sibling, Parent, Parent)


class Grandparent(BaseRelationshipType):
	dbKey='grandparent'

setInference(Parent, Parent, Grandparent)

class AuntOrUncle(BaseRelationshipType):
	dbKey='aunt/uncle'

setInference(Parent, Sibling, AuntOrUncle)

class Nibling(BaseRelationshipType):
	dbKey='nibling'

setInverse(AuntOrUncle, Nibling)

class GreatAuntOrGreatUncle(BaseRelationshipType):
	dbKey='great aunt/uncle'

setInference(Grandparent, Sibling, GreatAuntOrGreatUncle)

# only used in tests
class Ancestor(BaseRelationshipType):
	dbKey='ancestor'
	transitive=True

RELATIONSHIP_TYPES = {
	'child': Child,
	'parent': Parent,
	'sibling': Sibling,
	'grandparent': Grandparent,
	'aunt/uncle': AuntOrUncle,
	'nibling': Nibling,
	'ancestor': Ancestor,
	'great-aunt/uncle': GreatAuntOrGreatUncle,
	'half-sibling': HalfSibling,
}
RELATIONSHIP_TYPES = [
	Child,
	Parent,
	Sibling,
	Grandparent,
	AuntOrUncle,
	Nibling,
	Ancestor,
	GreatAuntOrGreatUncle,
	HalfSibling,
]
RELATIONSHIP_TYPE_CHOICES = []
for reltypeclass in RELATIONSHIP_TYPES:
	RELATIONSHIP_TYPE_CHOICES.append(
		(reltypeclass.dbKey, reltypeclass.__name__)
	)

def getRelationshipByTypeKey(key, subject, object):
	for reltypeclass in RELATIONSHIP_TYPES:
		if key == reltypeclass.dbKey:
			return reltypeclass(subject, object)
	raise Exception("Can't find relationship key "+key)