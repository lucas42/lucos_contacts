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
	label_ga = None
	label_en = None

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
	label_en='child'
	label_ga='páiste'

class Parent(BaseRelationshipType):
	dbKey='parent'
	label_en='parent'
	label_ga='tuismitheoir'

setInverse(Parent, Child)

# Applies only to full siblings (ie both parents are the same)
# See HalfSibling for relationships where only one parent is shared
class Sibling(BaseRelationshipType):
	dbKey='sibling'
	transitive=True
	label_en='sibling'
	label_ga='siblín'
class HalfSibling(BaseRelationshipType):
	dbKey='half-sibling'
	label_en='half-sibling'
	label_ga='leath-siblín'

setSymmetrical(Sibling)
setSymmetrical(HalfSibling)

setInference(Sibling, Parent, Parent)
setInference(Sibling, HalfSibling, HalfSibling)

class Grandchild(BaseRelationshipType):
	dbKey='grandchild'
	label_en='grandchild'
	label_ga='garpháiste'
class Grandparent(BaseRelationshipType):
	dbKey='grandparent'
	label_en='grandparent'
	label_ga='seantuismitheoir'

setInverse(Grandparent, Grandchild)

setInference(Parent, Parent, Grandparent)

class AuntOrUncle(BaseRelationshipType):
	dbKey='aunt/uncle'
	label_en='aunt/uncle'

setInference(Parent, Sibling, AuntOrUncle)
setInference(Sibling, AuntOrUncle, AuntOrUncle)

class Nibling(BaseRelationshipType):
	dbKey='nibling'
	label_en='nibling'
	label_ga='niblín'

setInverse(AuntOrUncle, Nibling)

class GreatAuntOrGreatUncle(BaseRelationshipType):
	dbKey='great aunt/uncle'
	label_en='great aunt/uncle'

setInference(Grandparent, Sibling, GreatAuntOrGreatUncle)
setInference(Sibling, GreatAuntOrGreatUncle, GreatAuntOrGreatUncle)

class GreatNibling(BaseRelationshipType):
	dbKey='great nibling'
	label_en='great nibling'
	label_ga='garniblín'

setInverse(GreatAuntOrGreatUncle, GreatNibling)

class FirstCousin(BaseRelationshipType):
	dbKey='first cousin'
	label_en='cousin'
	label_ga='col ceathrair'
setInference(AuntOrUncle, Child, FirstCousin)

RELATIONSHIP_TYPES = [
	Child,
	Parent,
	Sibling,
	HalfSibling,
	Grandchild,
	Grandparent,
	AuntOrUncle,
	Nibling,
	GreatAuntOrGreatUncle,
	GreatNibling,
	FirstCousin,
]
RELATIONSHIP_TYPE_CHOICES = []
for reltypeclass in RELATIONSHIP_TYPES:
	RELATIONSHIP_TYPE_CHOICES.append(
		(reltypeclass.dbKey, (reltypeclass.label_ga or reltypeclass.label_en).title())
	)

def getRelationshipTypeByKey(key):
	for reltypeclass in RELATIONSHIP_TYPES:
		if key == reltypeclass.dbKey:
			return reltypeclass()
	raise Exception("Can't find relationship key "+key)