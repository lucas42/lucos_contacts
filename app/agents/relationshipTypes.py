class BaseRelationshipType:
	def __init__(self, inverse = None):
		self.inverse = inverse
		if inverse:
			inverse.inverse = self
	def getInverse(self):
		return self.inverse