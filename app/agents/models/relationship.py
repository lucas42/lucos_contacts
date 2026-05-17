# -*- coding: utf-8 -*-
from django.db import models
from .relationshipTypes import RELATIONSHIP_TYPE_CHOICES, getRelationshipTypeByKey, RELATIONSHIP_TYPES
from .agent import Person
from django.db.models.functions import Lower


class RelationshipRefusedError(Exception):
	"""
	Raised when Relationship.delete() cannot proceed because the targeted row
	(plus its inverse/symmetric pair) would be re-inferred from the remaining
	graph after deletion.

	Attributes:
	    supporting_paths: list of human-readable strings describing the inference
	                      chains that re-produce the relationship.
	"""
	def __init__(self, supporting_paths):
		self.supporting_paths = supporting_paths
		super().__init__(self._make_message())

	def _make_message(self):
		lines = ["This relationship can't be removed because it's implied by:"]
		for path in self.supporting_paths:
			lines.append(f"– {path}")
		lines.append("\nTo remove it, first remove one of those relationships.")
		return "\n".join(lines)


class SiblingGroupExpansionRequired(Exception):
	"""
	Raised when deleting the targeted row(s) would be refused due solely to
	sibling-propagation re-inference, but expanding the staged set to cover the
	full sibling group of the target's object passes the closure check.

	The caller (typically the admin delete_view) is expected to present a
	confirmation prompt before performing the expanded deletion.

	Attributes:
	    staged_rows: frozenset of (subject_id, object_id, rel_type_key) tuples
	                 — the full expanded set to delete on confirmation.
	    sibling_members: list of Person objects that are in the target's sibling
	                     group (excluding the original target's object).
	"""
	def __init__(self, staged_rows, sibling_members):
		self.staged_rows = staged_rows
		self.sibling_members = sibling_members
		super().__init__(self._make_message())

	def _make_message(self):
		names = [p.getName() for p in self.sibling_members]
		count = len(names)
		if count == 0:
			return "Removing this relationship requires also removing related sibling relationships."
		if count <= 4:
			names_str = ", ".join(names)
		else:
			names_str = ", ".join(names[:3]) + f" and {count - 3} others"
		return f"Removing this relationship also removes it from: {names_str}. Remove all?"


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
		super(Relationship, self).save(*args, **kwargs)
		self.inferRelationships()

	def inferRelationships(self):
		relationshipType = getRelationshipTypeByKey(self.relationshipType)
		if relationshipType.transitive:
			others = Relationship.objects.filter(subject=self.object, relationshipType=relationshipType.dbKey).exclude(object=self.subject)
			for item in others:
				Relationship.objects.get_or_create(subject=self.subject, object=item.object, relationshipType=relationshipType.dbKey)
			others = Relationship.objects.filter(object=self.subject, relationshipType=relationshipType.dbKey).exclude(subject=self.object)
			for item in others:
				Relationship.objects.get_or_create(subject=item.subject, object=self.object, relationshipType=relationshipType.dbKey)
		if relationshipType.inverse:
			Relationship.objects.get_or_create(subject=self.object, object=self.subject, relationshipType=relationshipType.inverse.dbKey)
		for connection in relationshipType.outgoingRels:
			for existingRel in Relationship.objects.filter(subject=self.object, relationshipType=connection.existingRel.dbKey):
				Relationship.objects.get_or_create(subject=self.subject, object=existingRel.object, relationshipType=connection.inferredRel.dbKey)
		for connection in relationshipType.incomingRels:
			for existingRel in Relationship.objects.filter(object=self.subject, relationshipType=connection.existingRel.dbKey):
				Relationship.objects.get_or_create(subject=existingRel.subject, object=self.object, relationshipType=connection.inferredRel.dbKey)

	def _build_staged_set(self):
		"""
		Stage the deletion target plus its inverse/symmetric pair (if present).

		Returns a frozenset of (subject_id, object_id, rel_type_key) tuples.
		"""
		subj_id = self.subject_id
		obj_id = self.object_id
		rel_key = self.relationshipType
		rel_type = getRelationshipTypeByKey(rel_key)

		staged = {(subj_id, obj_id, rel_key)}

		if rel_type.inverse:
			inv_key = rel_type.inverse.dbKey
			if Relationship.objects.filter(
				subject_id=obj_id, object_id=subj_id, relationshipType=inv_key
			).exists():
				staged.add((obj_id, subj_id, inv_key))

		return frozenset(staged)

	def _compute_sibling_group_expansion(self, staged, db_rows):
		"""
		Expand staged to eliminate re-inference of the staged set.

		Two strategies are combined:

		Strategy 1 — target IS a sibling row (transitive propagation):
		    Expand to the full sibling group of the target's object, staging
		    all subject→member and member→subject sibling rows that exist in
		    db_rows.  This covers the common case where deleting one sibling
		    pair would be re-inferred via other members of the group.

		Strategy 2 — staged row is inferred from a sibling+T→T rule:
		    (A, sibling, B) + (B, T, C) → (A, T, C)

		    When (A, T, C) is staged, also stage (B, T, C) — the direct fact
		    that drives the inference — rather than staging the sibling row.
		    Only applies to same-type rules (where existingRel == inferredRel),
		    which covers all of Sibling's outgoingRels:
		      sibling + parent        → parent
		      sibling + half-sibling  → half-sibling
		      sibling + aunt/uncle    → aunt/uncle
		      sibling + great-aunt/uncle → great-aunt/uncle

		    Rules where the types differ (e.g. parent + sibling → aunt/uncle)
		    cannot be resolved by expansion and fall through to the refusal page.
		"""
		expanded = set(staged)
		rows_set = frozenset(db_rows)

		# ── Strategy 1: target IS a sibling — expand to full sibling group ──────
		if self.relationshipType == 'sibling':
			subj_id = self.subject_id
			obj_id = self.object_id
			# Sibling group of the target's object (everything obj_id is sibling of)
			sibling_group = {obj_id}
			for s, o, k in rows_set:
				if k == 'sibling' and s == obj_id:
					sibling_group.add(o)
			for member_id in sibling_group:
				if (subj_id, member_id, 'sibling') in rows_set:
					expanded.add((subj_id, member_id, 'sibling'))
				if (member_id, subj_id, 'sibling') in rows_set:
					expanded.add((member_id, subj_id, 'sibling'))

		# ── Strategy 2: staged rows inferred via sibling + T → T ─────────────────
		# For each rule (A, sibling, B) + (B, T, C) → (A, T, C):
		# when (A, T, C) is staged, also stage (B, T, C).
		# Do NOT stage the sibling row — only the same-type direct fact is staged.
		sibling_type = getRelationshipTypeByKey('sibling')
		for target_subj, target_obj, target_rel_key in list(staged):
			for conn in sibling_type.outgoingRels:
				# All of Sibling's outgoingRels are same-type (existingRel == inferredRel),
				# so conn.existingRel.dbKey == conn.inferredRel.dbKey == target_rel_key.
				if conn.inferredRel.dbKey == target_rel_key:
					other_key = conn.existingRel.dbKey
					for s, o, k in rows_set:
						if k == 'sibling' and s == target_subj:
							if (o, target_obj, other_key) in rows_set:
								# Stage (B, T, C) — the co-inferred direct fact
								expanded.add((o, target_obj, other_key))
								# Stage the inverse of (B, T, C) if it exists
								other_type = getRelationshipTypeByKey(other_key)
								if other_type.inverse:
									inv_key = other_type.inverse.dbKey
									if (target_obj, o, inv_key) in rows_set:
										expanded.add((target_obj, o, inv_key))

		return frozenset(expanded)

	def _get_supporting_paths(self, remaining_rows):
		"""
		Find all inference paths in remaining_rows that re-infer this relationship.

		Returns a list of dicts, each with:
		  - 'text': human-readable description of the inference path
		  - 'rel_pk': primary key of the first relationship in the path (for
		    linking to its admin change page), or None if the row cannot be found
		"""
		subj_id = self.subject_id
		obj_id = self.object_id
		rel_key = self.relationshipType
		rel_type = getRelationshipTypeByKey(rel_key)

		rows_set = frozenset(remaining_rows)

		# Collect all people IDs for name lookup
		all_ids = {subj_id, obj_id}
		for s, o, _ in rows_set:
			all_ids.add(s)
			all_ids.add(o)

		people = {p.pk: p.getName() for p in Person.objects.filter(pk__in=all_ids)}

		def name_of(person_id):
			return people.get(person_id, f'Person #{person_id}')

		def rel_display(key):
			try:
				return str(getRelationshipTypeByKey(key).label)
			except Exception:
				return key

		def lookup_pk(s_id, o_id, key):
			"""Return the PK of the first relationship in a path, or None."""
			try:
				return Relationship.objects.get(subject_id=s_id, object_id=o_id, relationshipType=key).pk
			except Relationship.DoesNotExist:
				return None

		paths = []

		# ── Transitive ────────────────────────────────────────────────────────
		# e.g. Alice is a sibling of Bob, and Bob is a sibling of Carol → Alice is a sibling of Carol
		if rel_type.transitive:
			for other_subj, other_obj, other_key in rows_set:
				if other_key == rel_key and other_subj == subj_id and other_obj != obj_id:
					if (other_obj, obj_id, rel_key) in rows_set:
						paths.append({
							'text': (
								f"{name_of(subj_id)} is a {rel_display(rel_key)} of {name_of(other_obj)}, "
								f"and {name_of(other_obj)} is a {rel_display(rel_key)} of {name_of(obj_id)}"
							),
							'rel_pk': lookup_pk(subj_id, other_obj, rel_key),
						})

		# ── SetInference rules ────────────────────────────────────────────────
		# Find all (rel1, rel2) pairs that produce rel_key as inferred type.
		# e.g. Alice is a parent of Bob, and Bob is a parent of Carol → Alice is a grandparent of Carol
		for rel1_class in RELATIONSHIP_TYPES:
			for conn in rel1_class.outgoingRels:
				if conn.inferredRel.dbKey == rel_key:
					# Rule: (Alice, rel1, Bob) + (Bob, rel2, Carol) → (Alice, rel_key, Carol)
					for other_subj, other_obj, other_key in rows_set:
						if other_key == rel1_class.dbKey and other_subj == subj_id:
							if (other_obj, obj_id, conn.existingRel.dbKey) in rows_set:
								paths.append({
									'text': (
										f"{name_of(subj_id)} is a {rel_display(rel1_class.dbKey)} of {name_of(other_obj)}, "
										f"and {name_of(other_obj)} is a {rel_display(conn.existingRel.dbKey)} of {name_of(obj_id)}"
									),
									'rel_pk': lookup_pk(subj_id, other_obj, rel1_class.dbKey),
								})

		return paths

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

	def delete(self, using=None, keep_parents=False):
		"""
		Delete this Relationship, enforcing the closure-check rule (ADR-0001).

		  1. Stages this row plus its inverse/symmetric pair.
		  2. Runs compute_closure on the hypothetical post-deletion state.
		  3. If the staged set is not re-inferred: deletes atomically, emits Loganne.
		  4. If the failure is due solely to transitive Sibling propagation and
		     the sibling-group expansion passes the check: raises
		     SiblingGroupExpansionRequired for the caller to handle.
		  5. Otherwise: raises RelationshipRefusedError with supporting paths.
		"""
		from agents.models.closure import compute_closure

		# ── Stage ─────────────────────────────────────────────────────────────
		staged = self._build_staged_set()

		# ── Load all DB rows ──────────────────────────────────────────────────
		db_rows = frozenset(
			(rel.subject_id, rel.object_id, rel.relationshipType)
			for rel in Relationship.objects.all()
		)

		# ── Closure check ─────────────────────────────────────────────────────
		remaining = db_rows - staged
		closure_of_remaining = compute_closure(remaining)
		re_inferred = staged & closure_of_remaining

		if not re_inferred:
			# Valid deletion — proceed
			self._perform_staged_deletion(staged)
			return

		# ── Try sibling-aware expansion ───────────────────────────────────────
		# Whether the target is itself a sibling row (transitive propagation) or
		# a non-sibling row implied by a sibling connection, the expansion may be
		# able to resolve the re-inference by staging the supporting sibling rows.
		expanded = self._compute_sibling_group_expansion(staged, db_rows)
		remaining_after_expansion = db_rows - expanded
		re_inferred_after = expanded & compute_closure(remaining_after_expansion)

		if not re_inferred_after:
			# Expansion passes — ask the caller to confirm
			extra_ids = set()
			for subj_id, obj_id, _ in expanded - staged:
				extra_ids.add(subj_id)
				extra_ids.add(obj_id)
			# Remove the original subject/object from the "extra" set
			extra_ids -= {self.subject_id, self.object_id}

			extra_people = list(
				Person.objects.filter(pk__in=extra_ids).order_by('_name')
			)
			raise SiblingGroupExpansionRequired(
				staged_rows=expanded,
				sibling_members=extra_people,
			)

		# ── Refuse ────────────────────────────────────────────────────────────
		paths = self._get_supporting_paths(remaining)
		raise RelationshipRefusedError(supporting_paths=paths)

	def getPriority(self):
		for index, choice in enumerate(RELATIONSHIP_TYPE_CHOICES):
			if choice[0] == self.relationshipType:
				return index
		return -1

	def __str__(self):
		return self.subject.getName()+" - "+self.get_relationshipType_display()+" - "+self.object.getName()
