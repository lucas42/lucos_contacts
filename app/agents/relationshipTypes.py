class BaseRelationshipType:
	inverse = None
	def __init__(self, subject, object):
		self.subject = subject
		self.object = object

	def getInverse(self):
		return self.inverse

def setInverse(typeA, typeB):
	if typeA.inverse or typeB.inverse:
		raise Exception("Inverse already set")
	typeA.inverse = typeB
	typeB.inverse = typeA

def setSymmetrical(relType):
	if relType.inverse:
		raise Exception("Inverse already set")
	relType.inverse = relType

class Child(BaseRelationshipType):
	pass

class Parent(BaseRelationshipType):
	pass

setInverse(Parent, Child)

class Sibling(BaseRelationshipType):
	pass

setSymmetrical(Sibling)