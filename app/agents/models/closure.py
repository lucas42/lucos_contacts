# -*- coding: utf-8 -*-
"""
Shared closure-computation utility for the relationship inference engine.

Used by:
  - agents.management.commands.audit_relationship_closure  (audit command)
  - agents.models.relationship                             (delete-time closure check)
"""
from .relationshipTypes import getRelationshipTypeByKey


def compute_closure(initial_rows):
	"""
	Compute the full inference closure of a set of relationship rows.

	Takes an iterable of (subject_id, object_id, rel_type_key) tuples and returns
	a frozenset of all rows that should exist once the inference engine has reached
	a fixed point.  This mirrors the logic in Relationship.inferRelationships() but
	operates on an in-memory snapshot rather than hitting the database.

	The algorithm is queue-based: each newly added row is processed exactly once,
	applying all four inference mechanisms (inverse, transitive, outgoingRels,
	incomingRels) against the current closure.  Because every rule fires in at least
	one direction (either when a row is first processed or when an existing row is
	the "other half" of the rule), the queue approach is equivalent to the fixed-point
	iteration but avoids redundant passes over the full set.
	"""
	closure = set(initial_rows)
	queue = list(closure)

	while queue:
		subj_id, obj_id, rel_key = queue.pop()
		rel_type = getRelationshipTypeByKey(rel_key)

		candidates = set()

		# ── Inverse ──────────────────────────────────────────────────────────
		# (A, T, B) → (B, T_inv, A)
		if rel_type.inverse:
			candidates.add((obj_id, subj_id, rel_type.inverse.dbKey))

		# ── Transitive ────────────────────────────────────────────────────────
		# (A, T, B) + (B, T, C) → (A, T, C)   [forward]
		# (X, T, A) + (A, T, B) → (X, T, B)   [backward]
		if rel_type.transitive:
			for other_subj, other_obj, other_key in closure:
				if other_key == rel_key:
					if other_subj == obj_id and other_obj != subj_id:
						candidates.add((subj_id, other_obj, rel_key))
					if other_obj == subj_id and other_subj != obj_id:
						candidates.add((other_subj, obj_id, rel_key))

		# ── OutgoingRels ──────────────────────────────────────────────────────
		# For setInference(rel1, rel2, inferred): (A, rel1, B) + (B, rel2, C) → (A, inferred, C)
		# When processing (A, rel1, B), look for (B, rel2, C) in closure.
		for conn in rel_type.outgoingRels:
			for other_subj, other_obj, other_key in closure:
				if other_key == conn.existingRel.dbKey and other_subj == obj_id:
					candidates.add((subj_id, other_obj, conn.inferredRel.dbKey))

		# ── IncomingRels ──────────────────────────────────────────────────────
		# For setInference(rel1, rel2, inferred): (A, rel1, B) + (B, rel2, C) → (A, inferred, C)
		# When processing (B, rel2, C), look for (A, rel1, B) in closure.
		for conn in rel_type.incomingRels:
			for other_subj, other_obj, other_key in closure:
				if other_key == conn.existingRel.dbKey and other_obj == subj_id:
					candidates.add((other_subj, obj_id, conn.inferredRel.dbKey))

		for candidate in candidates:
			if candidate not in closure:
				closure.add(candidate)
				queue.append(candidate)

	return frozenset(closure)
