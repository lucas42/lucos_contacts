from django.db import models
from django.utils.translation import gettext_lazy as _
from agents.models import Agent

class OccasionType(models.TextChoices):
	CHRISTMAS = 'Christmas', _('Christmas')
	BIRTHDAY = 'Birthday', _('Birthday')
	OTHER = 'Other', _('Other')

class OccasionList(models.Model):
	type = models.CharField(
		max_length=20,
		choices=OccasionType.choices,
		default=OccasionType.OTHER,
	)
	year = models.IntegerField(help_text="Calendar year, as per the Gregorian Calendar (Common Era assumed)")
	gave_card_to = models.ManyToManyField(Agent, related_name='gave_card_to', blank=True)
	received_card_from = models.ManyToManyField(Agent, related_name='received_card_from', blank=True)

	class Meta:
		unique_together = ('type', 'year')  # Ensure type and year combination is unique

	def __str__(self):
		return _("{year} {type} List").format(year=self.year, type=self.get_type_display())

GIVEN_CHOICES = ((True, 'Given'), (False, 'Received'))

class Present(models.Model):
	occasion = models.ForeignKey(OccasionList, on_delete=models.CASCADE, related_name="presents", null=True, blank=True)
	agents = models.ManyToManyField(Agent, related_name='presents', blank=True)
	was_given = models.BooleanField(help_text="Whether I gave or received the present", choices=GIVEN_CHOICES, default=True)
	description = models.CharField(max_length=255, help_text=_("E.g. 'Handmade Scarf', 'Book'"))

	def __str__(self):
		action = _("Given") if self.was_given else _("Received")
		agents = ", ".join(str(agent) for agent in self.agents.all())
		return _("{action} by {agents}: {description} ({occasion})").format(action=action, agents=agents, description=self.description, occasion=self.occasion)

class BirthdayPresent(Present):
	year = models.IntegerField()

	def __str__(self):
		action = _("Given") if self.was_given else _("Received")
		agents = ", ".join(str(agent) for agent in self.agents.all())
		return _("{description} for {agents}'s {year} Birthday").format(agents=agents, description=self.description, year=self.year)
