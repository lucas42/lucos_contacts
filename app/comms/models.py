from django.db import models
from django.utils.translation import gettext_lazy as _
from agents.models import Person

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
	year = models.IntegerField(_('year'), help_text=_("Calendar year, as per the Gregorian Calendar (Common Era assumed)"))
	gave_card_to = models.ManyToManyField(Person, related_name='gave_card_to', blank=True, verbose_name=_('gave card to'))
	received_card_from = models.ManyToManyField(Person, related_name='received_card_from', blank=True, verbose_name=_('received card from'))

	class Meta:
		unique_together = ('type', 'year')  # Ensure type and year combination is unique
		verbose_name = _('occasion list')
		verbose_name_plural = _('occasion lists')

	def __str__(self):
		return _("{year} {type} List").format(year=self.year, type=self.get_type_display())

GIVEN_CHOICES = ((True, _('Given')), (False, _('Received')))

class Present(models.Model):
	occasion = models.ForeignKey(OccasionList, on_delete=models.CASCADE, related_name="presents", null=True, blank=True, verbose_name=_('occasion'))
	agents = models.ManyToManyField(Person, related_name='presents', blank=True, verbose_name=_('agent'))
	was_given = models.BooleanField(_('was given'), help_text=_("Whether I gave or received the present"), choices=GIVEN_CHOICES, default=True)
	description = models.CharField(_('description'), max_length=255, help_text=_("E.g. 'Handmade Scarf', 'Book'"))

	class Meta:
		verbose_name = _('present')
		verbose_name_plural = _('presents')
	def __str__(self):
		action = _("Given to") if self.was_given else _("Received from")
		agents = ", ".join(str(agent) for agent in self.agents.all())
		return _("{action} {agents}: {description} ({occasion})").format(action=action, agents=agents, description=self.description, occasion=self.occasion)

class BirthdayPresent(Present):
	year = models.IntegerField(_('year'), help_text=_("The calendar year of the birthday the present was for (which is usually, but not necessarily, the year the present was given)"))

	class Meta:
		verbose_name = _('birthday present')
		verbose_name_plural = _('birthday presents')
	def __str__(self):
		action = _("Given") if self.was_given else _("Received")
		agents = ", ".join(str(agent) for agent in self.agents.all())
		return _("{description} for {agents}'s {year} Birthday").format(agents=agents, description=self.description, year=self.year)