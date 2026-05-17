# ADR-0002: Relationship inference engine consolidation

**Date:** 2026-05-17
**Status:** Proposed
**Discussion:** https://github.com/lucas42/lucos_contacts/issues/701
**Amends:** ADR-0001 (relationship-deletion-semantics)

## Context

ADR-0001 introduced the closure-check rule for relationship deletion and shipped via PR #705 on 2026-05-17. The shipped implementation is consistent with ADR-0001's invariants but exposes two structural problems that ADR-0001 did not address.

### Three consumers of the same rule set, each implemented differently

The inference rules in `agents/models/relationshipTypes.py` are walked by three independent pieces of code:

- **Save-time** — `Relationship.inferRelationships()` mutates the DB row by row via `get_or_create()`. Reaches the fixed point implicitly, because each new row's `save()` triggers another round of `inferRelationships()`.
- **Delete-time** — `compute_closure()` in `agents/models/closure.py` is a pure-function snapshot engine. Queue-based fixed-point iteration over an in-memory set of row tuples.
- **Audit-time** — `compute_closure()` in `agents/management/commands/audit_relationship_closure.py` — a second copy of the delete-time function. `closure.py`'s docstring claims the audit command uses the shared utility; it does not. The function was copy-pasted, and any future edit to one will silently fail to land in the other.

The `audit_relationship_closure` command exists to detect when these consumers disagree. That a separate audit command is needed to detect drift between consumers of the same declarative rule set is the smell.

### Supporting-path enumeration is structurally incomplete

`Relationship._get_supporting_paths()` walks the rule set forward — for each relationship type, iterate `outgoingRels`, look for inference rules whose inferred output is the refused row's type, and check whether the antecedent rows exist in the remaining graph. This covers:

- Direct 2-step transitive chains (A T X + X T B).
- Direct SetInference rules whose inferred output is the target type (one rule application).

It does not cover:

- Inverse rules. There is no `inverse` handling in `_get_supporting_paths()` at all.
- Transitive chains of length > 2.
- SetInference chains of length > 1 — i.e. cases where the antecedent of the producing rule is itself an inferred row.
- Inverse-of-inferred — a row inferred by inverse from a SetInference output.

lucas42 reported on PR #705 that he had hit cases where deletion is refused but the supporting-paths list comes back empty. The PR #705 developer admitted they could not reproduce the case from code analysis alone. The reason is structural: enumerating forward, one rule application at a time, will always miss any path that requires multiple rule applications. With Strategy 2b's removal in PR #705, the mixed-type sibling-propagation rules (`Parent + Sibling → AuntOrUncle`, `Grandparent + Sibling → GreatAuntOrGreatUncle`) now correctly route to refusal — and those are precisely the chains the forward enumeration misses.

### Exception-driven outcome protocol

`Relationship.delete()` raises one of `RelationshipRefusedError` or `SiblingGroupExpansionRequired` to signal which case applies. The single caller (`RelationshipAdmin.delete_view`) uses `try`/`except` blocks reading as flow control, not error handling. Both exception types exist solely to communicate a structured outcome; if we have a structured outcome, the exception scaffolding is noise.

### Sibling-aware expansion has two strategies in the shipped code, but ADR-0001 only describes one

ADR-0001 §"Sibling-group expansion" describes Strategy 1: staging the full sibling group `(A, T, Bj)` when the target is itself a sibling row. The shipped `_compute_sibling_group_expansion()` also implements Strategy 2: when the target `(A, T, C)` was inferred via a same-type sibling-propagation rule `(A, sibling, B) + (B, T, C) → (A, T, C)`, the expansion also stages `(B, T, C)` — the driving fact. lucas42 explicitly directed this on the PR #705 review thread, but ADR-0001's text does not cover it.

This ADR ratifies Strategy 2 in writing and amends ADR-0001 accordingly. The amendments are listed in §"Amendments to ADR-0001" below.

## Decision

### A single engine module

Replace the three current implementations with a single module — working name `agents.engine`, final location at implementer's discretion — exposing pure-function operations over `(subject_id, object_id, rel_type_key)` row tuples. Three public operations:

#### 1. `closure(rows) -> ClosureResult`

Replaces both copies of `compute_closure()`. Returns a `ClosureResult` carrying:

- `rows: frozenset[Row]` — the closed set.
- `trace: dict[Row, list[Derivation]]` — for each row in `rows` that was derived (not in the input), the chain(s) of facts and rule applications that produced it. A `Derivation` records `(rule_id, input_rows: tuple[Row, ...])`.

A row may be derivable multiple ways; the trace must record all of them so the reverse-walk shows every supporting path.

The trace is the single source of truth for explaining why any row in the closure exists. Everything else in this ADR is built on it.

#### 2. `add(row, rows) -> frozenset[Row]`

Returns the rows the engine would materialise on save, given an existing set. Equivalent to `closure(rows | {row}).rows - rows - {row}`. Exposed as a named operation so the save path is a one-liner; the trace can be skipped if performance ever matters (it doesn't at current scale).

`Relationship.save()` becomes a thin wrapper:

```python
def save(self, *args, **kwargs):
    super().save(*args, **kwargs)
    existing = current_db_rows()
    new_rows = engine.add(self._tuple(), existing)
    Relationship.objects.bulk_create(
        [Relationship(subject_id=s, object_id=o, relationshipType=k)
         for s, o, k in new_rows]
    )
```

Replaces `inferRelationships()`. (See "Negative consequences" below for the signal-firing caveat.)

#### 3. `plan_deletion(target_row, rows) -> DeletionPlan`

Returns a discriminated union with three variants:

- **`Safe(staged: frozenset[Row])`** — deletion proceeds. The caller deletes the staged rows atomically.
- **`RefusedWithPaths(staged: frozenset[Row], paths: list[InferencePath])`** — deletion refused. `paths` enumerated by walking the trace of `closure(rows - staged)` and selecting the derivations that produce each row in `staged ∩ closure_rows`. Recursive — chains of arbitrary depth fall out for free.
- **`ExpansionProposed(staged: frozenset[Row], extras: frozenset[Row], reason: ExpansionReason)`** — deletion possible but only after sibling-aware expansion. `extras = expanded - original_staged`. `reason` discriminates between the two expansion strategies (see ADR-0001 §"Sibling-group expansion" as amended).

`Relationship.delete()` becomes a thin wrapper that returns the plan. The single caller (`RelationshipAdmin.delete_view`) dispatches on `plan.kind`. The `RelationshipRefusedError` and `SiblingGroupExpansionRequired` exceptions are removed.

### Supporting-path enumeration via trace reverse-walk

The new `RefusedWithPaths.paths` is constructed by walking the `trace` of `closure(rows - staged)` backwards. For each `r in staged ∩ closure_rows`:

1. Look up `trace[r]` — the list of derivations that produced `r`.
2. For each derivation, recursively expand any input row that is itself derived, terminating at input rows that are in `rows - staged` directly.
3. Collect each grounded chain as an `InferencePath`.

The result is a DAG of grounded derivation paths, every one of which is a real path in the closure computation. Multi-step transitive chains, chained SetInference rules, inverse rules, inverse-of-inferred, and anything else the engine adds in the future are all covered by construction — because the trace records whatever the engine actually did.

Rendering is a thin formatter over `InferencePath`. The existing template format (`"X is a sibling of Y, and Y is a parent of Z"`) is unchanged.

### Audit command lifecycle

The audit command (`audit_relationship_closure`) is **not retired**. It is repurposed:

- Drift between save-time and closure-time engines is no longer possible (they are the same code path). That justification for the command falls away.
- The command continues to compare `closure(db_rows).rows` against `db_rows` to detect rows that *should* exist but don't, and rows that *exist* but the engine considers extraneous (always `{}` under purely additive rules, but the section is retained for completeness and to defend against future non-additive rule changes).
- This becomes useful as a one-shot data audit after **any rule change in `relationshipTypes.py`**. Rule changes will be rare; running the audit after each one is a sensible discipline.
- The duplicated `compute_closure` is removed; the command imports from the engine.
- The `--apply-missing` flag is retained; its semantics are unchanged.

If, in the future, the engine guarantees on-write that the DB is always closed (e.g. by running the audit as part of any rule-change migration), the command could be retired. That's a future call; out of scope here.

### Locking posture

This ADR does **not** introduce row-level locking around the closure check + delete. ADR-0001's "Implementation notes" mentioned `transaction.atomic` and `savepoint_rollback`; PR #705 did not implement them; this ADR ratifies that choice.

The application has a single admin user (lucas42), the data is small, and the bulk-confirm POST already re-runs the closure check before committing — catching the only race window that matters. Wrapping the read+check+delete in `SELECT … FOR UPDATE` would serialise admin operations for negligible benefit at this scale.

If `lucos_contacts` ever grows multiple concurrent writers, this decision must be revisited. Explicit assumption: single-writer, soft race-detection on POST, no row-level locking.

### Non-goals

- **Rule semantics do not change.** This ADR restructures the engine; it does not redefine what the engine computes.
- **The single declarative source of truth in `relationshipTypes.py` is unchanged.** The consolidation is about its *consumers*, not the source.
- **No new admin flows.** The three UX outcomes (refusal, sibling-group bulk-delete, same-type sibling-propagation expansion) are exactly what shipped in PR #705.
- **No performance optimisation beyond removing duplicate code.** Pre-computing or caching the closure is not in scope.

## Amendments to ADR-0001

ADR-0001 is updated in the same PR as this ADR:

1. **Status: Proposed → Accepted.** Implementation shipped via PR #705 on 2026-05-17.
2. **§"Sibling-group expansion" is rewritten** to describe both Strategy 1 (target is a sibling row, stage the full sibling group) and Strategy 2 (target inferred via a same-type sibling-propagation rule, stage the driving fact). The restriction to same-type rules is essential — Strategy 2 must not stage rows of a different type from a different person's relationship set, because that would cross the "user did not point at this row" line that the bulk-delete confirmation flow is meant to respect.
3. **§"Refusal and confirmation UX" is updated** to recognise three distinct outcomes: refusal, sibling-group bulk-delete confirmation (Strategy 1), and same-type sibling-propagation confirmation (Strategy 2). The bulk-delete template is reused across both confirmation variants; the copy distinguishes them.

The amendments are descriptive of shipped behaviour — they do not change what the system does, only what the ADR says it does.

## Alternatives considered

### Keep two engines, patch the supporting-path bug in place

Patch `_get_supporting_paths()` to recurse through inverse rules and chained SetInference. Patch the audit command to import `compute_closure` from `closure.py`. Leave `inferRelationships()` alone.

Rejected. The drift-by-construction problem stays. The save-time and closure-time engines continue to encode the same rules in two different shapes; every future rule addition still needs wiring into both. The audit command's reason for existing would still apply.

The supporting-path fix in isolation is also fiddlier than it looks: recursing through the existing forward-walk code without producing duplicate paths or infinite loops is harder than walking a closure trace, because the trace already records grounded chains by construction.

### Exception-driven outcome protocol retained

Keep `RelationshipRefusedError` and `SiblingGroupExpansionRequired` at the model boundary; have `Relationship.delete()` raise them, with the engine called internally.

Rejected. The exceptions exist solely to communicate a structured outcome. If we have a structured outcome, the indirection adds noise without insulating any caller — there is one in-tree caller (the admin `delete_view`), and updating it to dispatch on `plan.kind` is a few lines. Keeping the exceptions would mean every future caller has to know two sentinel types; removing them means every future caller sees a typed return.

### Transactional locking with `SELECT ... FOR UPDATE`

Wrap read+check+delete in a single transaction with row-level locks. Eliminates the GET-POST race window without the soft re-check.

Rejected on cost-vs-benefit. Single-writer admin app, low row count, soft re-check already in place. Locking would serialise admin operations for a race window that is practically empty.

### Materialise the trace into the database

Persist the derivation trace alongside the closure rows. Eliminates the closure recompute on every delete attempt.

Rejected as premature. The closure recompute is fast at current scale. Materialising the trace would add a second source of truth (the trace table) that needs to stay in sync with the rows table, bringing back drift-by-construction in a different form. Reconsider only if performance becomes a real concern.

## Consequences

### Positive

- **Single engine.** One walker of the inference rules, used by save, delete, and audit. New rules in `relationshipTypes.py` only need wiring in one place. Drift-by-construction goes away.
- **Supporting-path enumeration is complete.** All chains, all depths, all rule types — by construction. lucas42's reported empty-paths case is fixed structurally; it cannot recur as long as the trace records whatever the engine did.
- **Structured outcome.** `DeletionPlan` makes the admin code's dispatch explicit and removes the try/except-as-flow-control pattern.
- **Audit command stays useful** as a post-rule-change data audit, rather than as a drift detector for code that should not have drifted in the first place.
- **ADR-0001 catches up with the implementation** — Strategy 2 is in writing, the third UX flow is in writing, the status reflects shipped reality.

### Negative

- **Migration touches every save and every delete.** The behavioural surface stays the same, but the code path changes. Every test that exercises save or delete must continue to pass without changes to test bodies (the issue's acceptance criteria require this). Risk is mitigated by the harness tests from #699 and the journey tests from #700 / PR #705, but the migration is still the single riskiest step in this work programme.
- **`bulk_create` in `save()` skips Django signals on the inferred rows.** Today, each inferred row's `save()` fires `post_save` signals (and any signal handlers attached to them). After consolidation, the inferred rows are written via `bulk_create` and signals do not fire for them. At present `lucos_contacts` does not appear to depend on `post_save` for `Relationship`, but the implementer **must verify before shipping**. If a signal dependency surfaces, either iterate `Relationship.objects.create(...)` per row (slower, signals fire), or migrate the signal to listen on the engine's `add()` boundary explicitly. This is a behavioural change worth calling out.
- **Exception removal is a small API break** for any out-of-tree caller of `Relationship.delete()`. In practice the only callers are `RelationshipAdmin.delete_view` (updated to dispatch on `DeletionPlan`), `_merge_two_agents` (which uses queryset `delete()` to bypass the model method — unaffected), and the test suite (which will need its assertions updated).
- **Performance unchanged at current scale; potential regression at large scale.** The trace is more memory per closure call than the bare set. Negligible now; worth flagging if data grows by an order of magnitude or more.
- **The skip-locking decision is now explicit, not implicit.** A future contributor working under different assumptions (e.g. enabling external API writes, multi-admin access) must remember to revisit this. Flagged here; the future contributor's job to read it.

## Implementation notes (non-normative)

For the implementing teammate:

- **Build the engine module first, with its own unit tests against the rule set.** Get the engine green against its own tests before wiring `save()` / `delete()` through it. The post-migration gate is that the following existing test classes continue to pass without test-body changes:
  - `agents/tests/models.py::RelationshipTest` — exercises the inference rules (symmetrical/transitive, inverse, two-leg inference, complicated chains, duplicate prevention).
  - `agents/tests/management_commands.py::ComputeClosureTest` — direct unit tests of the existing `compute_closure()` function. Once the engine replaces `compute_closure`, this class must keep passing against `engine.closure(...).rows`.
  - `agents/tests/management_commands.py::AuditCommandMissingRowTest`, `AuditCommandExtraneousRowTest`, `AuditCommandApplyMissingTest` — guard the audit command's behaviour after it switches to importing the engine.
  - `agents/tests/admin.py::RelationshipAdminDeletionJourneyTest` and `RelationshipInlineJourneyTest` — guard the three deletion journey outcomes (clean, refusal, expansion) and the inline-form delete-link routing.
  Note that issue #701's acceptance criteria reference a `RelationshipDeletionSemanticsTest` class — that name does not exist in the repo; the list above is the actual coverage. The principle is unchanged: test bodies don't move.
- **Trace shape.** `ClosureResult.trace` maps each derived row to a list of `Derivation` records. A `Derivation` is `(rule_id, input_rows: tuple[Row, ...])`. The list rather than a single derivation is essential: a row may be derivable multiple ways, and the reverse-walk needs all of them to show the user every supporting path.
- **`add(row, rows)`** can be implemented as `closure(rows | {row}).rows - rows - {row}` to keep the engine's public surface small. The cost of trace computation can be skipped in the `add` path if performance ever matters (it doesn't, at current scale).
- **`plan_deletion`** runs `closure(rows - staged)` to compute the post-deletion graph, then checks `staged & closure_result.rows`. If empty: `Safe(staged)`. Otherwise: compute the sibling-aware expansion (lift `_compute_sibling_group_expansion` into the engine, preserving Strategy 1 and Strategy 2 exactly), re-check, return `ExpansionProposed` or `RefusedWithPaths`.
- **Refused-paths construction** walks the trace of `closure(rows - staged)` for each `r in staged ∩ closure_result.rows`. Render each grounded path as a tuple of `(subject_name, rel_type_label, object_name)` segments the existing template can consume.
- **Audit command** imports the engine and replaces its inline `compute_closure`. Keep the CLI flags and the output format unchanged.
- **Loganne emission stays in `_perform_staged_deletion`** — no change there.
- **Run the audit command against the development database after the engine lands**, before any deploy. It is the canary for behavioural regression.
