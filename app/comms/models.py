from django.db import models
from agents.models import Agent

class ChristmasList(models.Model):

	# Calendar year, as per the Gregorian Calendar (Common Era assumed)
	year = models.IntegerField(primary_key=True, editable=False)
	gave_card_to = models.ManyToManyField(Agent, related_name='gave_card_to')
	received_card_from = models.ManyToManyField(Agent, related_name='received_card_from')

	def __str__(self):
		return str(self.year)+" Christmas List"