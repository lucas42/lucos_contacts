# -*- coding: utf-8 -*-
from django.db import models
from .relationshipTypes import RELATIONSHIP_TYPE_CHOICES, getRelationshipTypeByKey, RELATIONSHIP_TYPES
from .agent import Person
from django.db.models.functions import Lower


class Relationship(models.Model):
	subject = models.ForeignKey(Person, related_name='subject', blank=False, on_delete=models.CASCADE)
	object = models.ForeignKey(Person, related_name='object', blank=False, on_delete=models.CASCADE)
	relationshipType = models.CharField(choices=RELATIONSHIP_TYPE_CHOICES, blank=False, max_length=127)
	class Meta:
		# Ideally this would just be ['subject'], and then follow the Lower('_name') bit on the agent model
		# However, the `Lower` function seems to cause that to error in quite a cryptic way
		# So easiest fix is just be more explicit here
		# Note the the first two underscores are for separating the the model from the field; the third underscore is part of the field name.
		ordering = [Lower('subject___name')]
		unique_together = ('subject', 'object', 'relationshipType')

	def save(self, *args, **kwargs):
		"""
		Save this Relationship and materialise all inferred rows.

		Replaces the old inferRelationships() cascade.  After persisting this
		row via super().save(), the engine computes the full closure delta in
		one shot and bulk_creates all newly-implied rows.

		Note: bulk_create skips per-row save() signals on the inferred rows.
		Verified: lucos_contacts has no post_save signal dependency on Relationship.
		"""
		super(Relationship, self).save(*args, **kwargs)

		from agents.models import engine as _engine

		# Load all current rows excluding self (engine.add expects existing rows
		# without the row being saved)
		existing = frozenset(
			(rel.subject_id, rel.object_id, rel.relationshipType)
			for rel in Relationship.objects.exclude(pk=self.pk)
		)
		self_row = (self.subject_id, self.object_id, self.relationshipType)
		new_rows = _engine.add(self_row, existing)

		if new_rows:
			# Sort for deterministic insertion order — tests rely on PK order
			Relationship.objects.bulk_create(
				[
					Relationship(subject_id=s, object_id=o, relationshipType=k)
					for s, o, k in sorted(new_rows)
				],
				ignore_conflicts=True,
			)

	def delete(self, using=None, keep_parents=False):
		"""
		Compute and return the deletion plan for this Relationship (ADR-0002).

		Returns a DeletionPlan — one of Safe, ExpansionProposed, or
		RefusedWithPaths — rather than performing the deletion directly.

		The caller (RelationshipAdmin.delete_view) dispatches on plan.kind and
		performs the actual deletion via _perform_staged_deletion() when the
		plan is Safe or after the user confirms an ExpansionProposed.

		The old RelationshipRefusedError and SiblingGroupExpansionRequired
		exceptions have been removed; use plan.kind == 'refused' /
		plan.kind == 'expansion' instead.
		"""
		from agents.models import engine as _engine

		db_rows = frozenset(
			(rel.subject_id, rel.object_id, rel.relationshipType)
			for rel in Relationship.objects.all()
		)
		target_row = (self.subject_id, self.object_id, self.relationshipType)
		return _engine.plan_deletion(target_row, db_rows)

	@staticmethod
	def _perform_staged_deletion(staged_rows):
		"""
		Atomically delete all rows in staged_rows and emit a Loganne
		relationshipDeleted event per row after the transaction commits.
		"""
		from django.db import transaction
		from agents.loganne import relationshipDeleted

		# Capture names and PKs before deletion (FK objects still accessible)
		events = []
		staged_pks = []
		for subj_id, obj_id, rel_key in staged_rows:
			try:
				rel = Relationship.objects.get(
					subject_id=subj_id, object_id=obj_id, relationshipType=rel_key
				)
				staged_pks.append(rel.pk)
				events.append((
					rel.subject.getName(),
					rel.object.getName(),
					rel.get_relationshipType_display(),
				))
			except Relationship.DoesNotExist:
				pass

		captured_events = list(events)

		def emit():
			for subj_name, obj_name, rel_display in captured_events:
				relationshipDeleted(subj_name, obj_name, rel_display)

		with transaction.atomic():
			Relationship.objects.filter(pk__in=staged_pks).delete()
			transaction.on_commit(emit)

		return len(staged_pks)

	def getPriority(self):
		for index, choice in enumerate(RELATIONSHIP_TYPE_CHOICES):
			if choice[0] == self.relationshipType:
				return index
		return -1

	def __str__(self):
		return self.subject.getName()+" - "+self.get_relationshipType_display()+" - "+self.object.getName()
