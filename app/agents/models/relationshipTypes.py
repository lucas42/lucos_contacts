from django.utils.translation import gettext_lazy as _
from django.utils.functional import keep_lazy_text

# Lazily makes translation objects titlecase
@keep_lazy_text
def lazy_title(str):
	return str.title()

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
	label = None

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
	label=_('child')

class Parent(BaseRelationshipType):
	dbKey='parent'
	label=_('parent')

setInverse(Parent, Child)

# Applies only to full siblings (ie both parents are the same)
# See HalfSibling for relationships where only one parent is shared
class Sibling(BaseRelationshipType):
	dbKey='sibling'
	transitive=True
	label=_('sibling')
class HalfSibling(BaseRelationshipType):
	dbKey='half-sibling'
	label=_('half-sibling')

setSymmetrical(Sibling)
setSymmetrical(HalfSibling)

setInference(Sibling, Parent, Parent)
setInference(Sibling, HalfSibling, HalfSibling)

class Grandchild(BaseRelationshipType):
	dbKey='grandchild'
	label=_('grandchild')
class Grandparent(BaseRelationshipType):
	dbKey='grandparent'
	label=_('grandparent')

setInverse(Grandparent, Grandchild)

setInference(Parent, Parent, Grandparent)

class AuntOrUncle(BaseRelationshipType):
	dbKey='aunt/uncle'
	label=_('aunt/uncle')

setInference(Parent, Sibling, AuntOrUncle)
setInference(Sibling, AuntOrUncle, AuntOrUncle)

class Nibling(BaseRelationshipType):
	dbKey='nibling'
	label=_('nibling')

setInverse(AuntOrUncle, Nibling)

class GreatAuntOrGreatUncle(BaseRelationshipType):
	dbKey='great aunt/uncle'
	label=_('great aunt/uncle')

setInference(Grandparent, Sibling, GreatAuntOrGreatUncle)
setInference(Sibling, GreatAuntOrGreatUncle, GreatAuntOrGreatUncle)

class GreatNibling(BaseRelationshipType):
	dbKey='great nibling'
	label=_('great nibling')

setInverse(GreatAuntOrGreatUncle, GreatNibling)

class FirstCousin(BaseRelationshipType):
	dbKey='first cousin'
	label=_('cousin')
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
	FirstCousin,
	GreatAuntOrGreatUncle,
	GreatNibling,
]
RELATIONSHIP_TYPE_CHOICES = []
for reltypeclass in RELATIONSHIP_TYPES:
	RELATIONSHIP_TYPE_CHOICES.append(
		(reltypeclass.dbKey, lazy_title(reltypeclass.label))
	)

def getRelationshipTypeByKey(key):
	for reltypeclass in RELATIONSHIP_TYPES:
		if key == reltypeclass.dbKey:
			return reltypeclass()
	raise Exception("Can't find relationship key "+key)