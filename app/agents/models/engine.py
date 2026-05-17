# -*- coding: utf-8 -*-
"""
Single relationship inference engine (ADR-0002).

Three public operations over (subject_id, object_id, rel_type_key) row tuples:
  - closure(rows) -> ClosureResult
  - add(row, rows) -> frozenset[Row]
  - plan_deletion(target_row, rows) -> DeletionPlan

All operations are pure functions over tuple sets — no database access.
"""
import itertools
from dataclasses import dataclass, field
from typing import ClassVar

from .relationshipTypes import getRelationshipTypeByKey, RELATIONSHIP_TYPES


# ── Derivation ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Derivation:
    """
    Records a single rule application that produced a derived row.

    Attributes:
        rule_id:    String identifying which rule fired.
        input_rows: Tuple of Row tuples that were combined by the rule.
    """
    rule_id: str
    input_rows: tuple  # tuple[Row, ...]


# ── ClosureResult ─────────────────────────────────────────────────────────────

@dataclass
class ClosureResult:
    """
    Result of closure(rows).

    Attributes:
        rows:  frozenset of all (subject_id, object_id, rel_type_key) tuples
               in the closed set (includes input rows and derived rows).
        trace: dict mapping each *derived* row to the list of Derivation records
               that produced it.  Only rows NOT in the original input appear as
               keys.  A row may have multiple derivations if the same row is
               reachable via different rule applications.
    """
    rows: frozenset
    trace: dict  # dict[Row, list[Derivation]]


# ── DeletionPlan variants ─────────────────────────────────────────────────────

@dataclass
class Safe:
    """
    Deletion proceeds: the staged rows can be deleted safely.
    The closure of the remaining graph does not re-infer any staged row.
    """
    staged: frozenset  # frozenset[Row] — rows to delete atomically

    @property
    def kind(self):
        return 'safe'


@dataclass
class ExpansionProposed:
    """
    Deletion possible after sibling-aware expansion.

    The caller must present a confirmation step before performing the
    expanded deletion.

    Attributes:
        staged: Full expanded set to delete on confirmation (original_staged ∪ extras).
        extras: Rows beyond the original staged set added by the expansion.
        reason: 'sibling_group'      — Strategy 1: target is a sibling row; the
                                       full sibling group is staged.
                'sibling_propagation' — Strategy 2: target is inferred via a
                                       sibling + T → T rule; the co-inferred
                                       direct-type row is staged.
    """
    staged: frozenset  # frozenset[Row] — full expanded set
    extras: frozenset  # frozenset[Row] — rows added by expansion
    reason: str        # 'sibling_group' or 'sibling_propagation'

    @property
    def kind(self):
        return 'expansion'


@dataclass
class RefusedWithPaths:
    """
    Deletion refused.

    The staged rows would be re-inferred from the remaining graph, and
    sibling-aware expansion does not resolve the re-inference.

    Attributes:
        staged: Original staged set (not expanded).
        paths:  List of grounded derivation paths explaining re-inference of
                the target row.  Each path is a list of Row edges whose inputs
                are facts in the remaining graph.
    """
    staged: frozenset  # frozenset[Row] — original staged set
    paths: list        # list[list[Row]] — grounded derivation chains

    @property
    def kind(self):
        return 'refused'


# ── closure() ─────────────────────────────────────────────────────────────────

def closure(initial_rows):
    """
    Compute the full inference closure of a set of relationship rows.

    Takes an iterable of (subject_id, object_id, rel_type_key) tuples and
    returns a ClosureResult with:
      - rows:  frozenset of all rows in the closed set
      - trace: dict mapping each derived row to all Derivation records that
               produced it (derived rows only — not rows in initial_rows)

    Algorithm: queue-based fixed-point iteration.  Each newly added row is
    processed exactly once, applying the four inference mechanisms (inverse,
    transitive, outgoingRels, incomingRels).  All derivation paths are
    recorded: when a rule fires for a row already in the closure, the new
    Derivation is appended to trace[row] rather than discarded.  This is
    essential for complete supporting-path enumeration in plan_deletion.
    """
    initial_set = frozenset(initial_rows)
    closure_set = set(initial_set)
    queue = list(initial_set)
    trace_sets = {}  # dict[Row, set[Derivation]] — sets for deduplication

    while queue:
        subj_id, obj_id, rel_key = queue.pop()
        rel_type = getRelationshipTypeByKey(rel_key)

        # Collect (candidate, Derivation) pairs from all applicable rules
        candidate_derivations = []

        # ── Inverse ──────────────────────────────────────────────────────────
        # (A, T, B) → (B, T_inv, A)
        if rel_type.inverse:
            inv_row = (obj_id, subj_id, rel_type.inverse.dbKey)
            candidate_derivations.append((
                inv_row,
                Derivation(
                    rule_id=f'inverse:{rel_key}',
                    input_rows=((subj_id, obj_id, rel_key),),
                ),
            ))

        # ── Transitive ────────────────────────────────────────────────────────
        # (A, T, B) + (B, T, C) → (A, T, C)   [forward: processing A,T,B; finds B,T,C]
        # (X, T, A) + (A, T, B) → (X, T, B)   [backward: processing A,T,B; finds X,T,A]
        if rel_type.transitive:
            for other_subj, other_obj, other_key in closure_set:
                if other_key == rel_key:
                    if other_subj == obj_id and other_obj != subj_id:
                        # Forward: (subj, obj) + (obj, other_obj) → (subj, other_obj)
                        derived = (subj_id, other_obj, rel_key)
                        candidate_derivations.append((
                            derived,
                            Derivation(
                                rule_id=f'transitive:{rel_key}',
                                input_rows=((subj_id, obj_id, rel_key), (other_subj, other_obj, other_key)),
                            ),
                        ))
                    if other_obj == subj_id and other_subj != obj_id:
                        # Backward: (other_subj, subj) + (subj, obj) → (other_subj, obj)
                        derived = (other_subj, obj_id, rel_key)
                        candidate_derivations.append((
                            derived,
                            Derivation(
                                rule_id=f'transitive:{rel_key}',
                                input_rows=((other_subj, other_obj, other_key), (subj_id, obj_id, rel_key)),
                            ),
                        ))

        # ── OutgoingRels ──────────────────────────────────────────────────────
        # setInference(rel1, rel2, inferred): (A, rel1, B) + (B, rel2, C) → (A, inferred, C)
        # Processing (A, rel1, B): look for (B, rel2, C) in closure.
        for conn in rel_type.outgoingRels:
            for other_subj, other_obj, other_key in closure_set:
                if other_key == conn.existingRel.dbKey and other_subj == obj_id:
                    derived = (subj_id, other_obj, conn.inferredRel.dbKey)
                    candidate_derivations.append((
                        derived,
                        Derivation(
                            rule_id=(
                                f'setinference:{rel_key}+{conn.existingRel.dbKey}'
                                f'→{conn.inferredRel.dbKey}'
                            ),
                            input_rows=((subj_id, obj_id, rel_key), (other_subj, other_obj, other_key)),
                        ),
                    ))

        # ── IncomingRels ──────────────────────────────────────────────────────
        # setInference(rel1, rel2, inferred): (A, rel1, B) + (B, rel2, C) → (A, inferred, C)
        # Processing (B, rel2, C): look for (A, rel1, B) in closure.
        for conn in rel_type.incomingRels:
            for other_subj, other_obj, other_key in closure_set:
                if other_key == conn.existingRel.dbKey and other_obj == subj_id:
                    derived = (other_subj, obj_id, conn.inferredRel.dbKey)
                    candidate_derivations.append((
                        derived,
                        Derivation(
                            rule_id=(
                                f'setinference:{conn.existingRel.dbKey}+{rel_key}'
                                f'→{conn.inferredRel.dbKey}'
                            ),
                            input_rows=((other_subj, other_obj, other_key), (subj_id, obj_id, rel_key)),
                        ),
                    ))

        # ── Record derivations and enqueue new rows ───────────────────────────
        for candidate, derivation in candidate_derivations:
            # Only record trace for rows NOT in the original input
            if candidate not in initial_set:
                if candidate not in trace_sets:
                    trace_sets[candidate] = set()
                trace_sets[candidate].add(derivation)

            if candidate not in closure_set:
                closure_set.add(candidate)
                queue.append(candidate)

    trace = {row: list(derivations) for row, derivations in trace_sets.items()}
    return ClosureResult(rows=frozenset(closure_set), trace=trace)


# ── add() ─────────────────────────────────────────────────────────────────────

def add(row, rows):
    """
    Return the rows the engine would materialise on save, given existing rows.

    Equivalent to closure(rows | {row}).rows - rows - {row}.

    Args:
        row:  A (subject_id, object_id, rel_type_key) tuple being saved.
        rows: frozenset of existing rows (should NOT include row itself).

    Returns:
        frozenset of new rows to create (excludes row and all rows already
        in rows).
    """
    rows_set = frozenset(rows)
    return closure(rows_set | {row}).rows - rows_set - {row}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _build_staged(target_row, rows):
    """
    Build the initial staged set for deletion: target_row plus its
    inverse/symmetric pair if that pair exists in rows.

    Returns a frozenset.
    """
    subj_id, obj_id, rel_key = target_row
    rel_type = getRelationshipTypeByKey(rel_key)

    staged = {target_row}

    if rel_type.inverse:
        inv_row = (obj_id, subj_id, rel_type.inverse.dbKey)
        if inv_row in rows:
            staged.add(inv_row)

    return frozenset(staged)


def _compute_sibling_expansion(target_row, original_staged, rows):
    """
    Expand original_staged to attempt to resolve sibling-driven re-inference.

    Implements two strategies (ADR-0001 §"Sibling-group expansion", as amended):

    Strategy 1 (sibling_group) — target IS a sibling row:
        Expand to the full sibling group of the target's object, staging all
        subject→member and member→subject sibling rows that exist in rows.

    Strategy 2 (sibling_propagation) — staged row is inferred via sibling + T → T:
        For each staged row (A, T, C) inferred via (A, sibling, B) + (B, T, C) → (A, T, C),
        also stage (B, T, C) — the co-inferred direct-type fact.
        Only applies to same-type rules (existingRel == inferredRel).

    Returns (expanded_staged: frozenset, reason: str) where reason is
    'sibling_group' or 'sibling_propagation'.
    """
    subj_id, obj_id, rel_key = target_row
    expanded = set(original_staged)
    rows_set = frozenset(rows)

    # ── Strategy 1: target IS a sibling ──────────────────────────────────────
    if rel_key == 'sibling':
        # Collect the sibling group of the target's object
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
    # For (A, T, C) in original_staged: if there is (A, sibling, B) + (B, T, C) → (A, T, C),
    # also stage (B, T, C) and its inverse.  Only same-type rules (existingRel == inferredRel).
    sibling_type = getRelationshipTypeByKey('sibling')
    for target_subj, target_obj, target_rel_key in list(original_staged):
        for conn in sibling_type.outgoingRels:
            if conn.inferredRel.dbKey == target_rel_key:
                other_key = conn.existingRel.dbKey
                for s, o, k in rows_set:
                    if k == 'sibling' and s == target_subj:
                        if (o, target_obj, other_key) in rows_set:
                            # Stage (B, T, C) — the co-inferred direct fact
                            expanded.add((o, target_obj, other_key))
                            # Stage its inverse if it exists
                            other_type = getRelationshipTypeByKey(other_key)
                            if other_type.inverse:
                                inv_key = other_type.inverse.dbKey
                                if (target_obj, o, inv_key) in rows_set:
                                    expanded.add((target_obj, o, inv_key))

    expanded_frozen = frozenset(expanded)

    # Determine reason from what was added
    if all(k == 'sibling' for _, _, k in expanded_frozen):
        reason = 'sibling_group'
    else:
        reason = 'sibling_propagation'

    return expanded_frozen, reason


def _build_grounded_paths(row, trace, initial_rows, _visited=None):
    """
    Recursively walk the trace to find all grounded derivation paths for row.

    A grounded path is a list of Row edges where every edge is in initial_rows
    (a fact in the remaining graph, not itself derived).

    Returns a list of paths; each path is a list of Row tuples.
    """
    if _visited is None:
        _visited = frozenset()

    if row in _visited:
        return []  # cycle guard

    if row in initial_rows:
        return [[row]]  # base case: row is a fact

    if row not in trace:
        return []  # not derivable (should not happen for re-inferred rows)

    _visited = _visited | {row}

    all_paths = []
    seen_paths = set()

    for derivation in trace[row]:
        # Build grounded paths for each input row in this derivation
        input_path_lists = []
        groundable = True
        for input_row in derivation.input_rows:
            sub_paths = _build_grounded_paths(input_row, trace, initial_rows, _visited)
            if not sub_paths:
                groundable = False
                break
            input_path_lists.append(sub_paths)

        if not groundable:
            continue

        # Cross-product: combine one sub-path per input row
        for combo in itertools.product(*input_path_lists):
            flat = []
            for sub_path in combo:
                flat.extend(sub_path)
            path_key = tuple(flat)
            if path_key not in seen_paths:
                seen_paths.add(path_key)
                all_paths.append(list(flat))

    return all_paths


# ── plan_deletion() ───────────────────────────────────────────────────────────

def plan_deletion(target_row, rows):
    """
    Compute the deletion plan for target_row given the current row set.

    Args:
        target_row: (subject_id, object_id, rel_type_key) tuple to delete.
        rows:       Iterable of all current (subject_id, object_id, rel_type_key)
                    tuples (the full DB snapshot).  Must include target_row.

    Returns one of:
        Safe(staged)
            Deletion is safe; caller should delete all rows in staged atomically.
        ExpansionProposed(staged, extras, reason)
            Deletion possible after sibling-aware expansion.  staged is the full
            expanded set to delete.  extras are the rows added by expansion.
            reason discriminates the two expansion strategies.
        RefusedWithPaths(staged, paths)
            Deletion refused.  paths explains why target_row would be re-inferred
            from the remaining graph after deletion.
    """
    rows_set = frozenset(rows)

    # ── Stage target row plus its inverse/symmetric pair ─────────────────────
    staged = _build_staged(target_row, rows_set)

    # ── Closure check on post-deletion graph ─────────────────────────────────
    remaining = rows_set - staged
    result = closure(remaining)
    re_inferred = staged & result.rows

    if not re_inferred:
        return Safe(staged=staged)

    # ── Try sibling-aware expansion ───────────────────────────────────────────
    expanded, reason = _compute_sibling_expansion(target_row, staged, rows_set)
    remaining_after = rows_set - expanded
    result_after = closure(remaining_after)
    re_inferred_after = expanded & result_after.rows

    if not re_inferred_after:
        extras = expanded - staged
        return ExpansionProposed(staged=expanded, extras=extras, reason=reason)

    # ── Refuse: build supporting paths from the trace ─────────────────────────
    # Build paths for the target_row specifically (not all staged rows) to match
    # the single-row focus of the existing template.
    paths = _build_grounded_paths(target_row, result.trace, remaining)
    return RefusedWithPaths(staged=staged, paths=paths)
