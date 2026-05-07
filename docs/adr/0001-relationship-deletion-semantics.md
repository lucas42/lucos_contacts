# ADR-0001: Relationship deletion semantics

**Date:** 2026-05-07
**Status:** Proposed
**Discussion:** https://github.com/lucas42/lucos_contacts/issues/53

## Context

`lucos_contacts` models family relationships through a `Relationship` table whose rows are typed (parent, sibling, aunt/uncle, nibling, cousin, half-sibling, grandparent, grandchild, great aunt/uncle, great nibling). Saving any relationship triggers an inference engine in `Relationship.inferRelationships()` which materialises further rows: inverses (parent ↔ child), transitive closure (sibling chains), and multi-relation chains (e.g. "parent of B + sibling of C → aunt/uncle of C").

Today, deletion is not symmetric with creation. `Relationship.delete()` removes only the targeted row. Inverses, transitively-implied relationships, and multi-relation entailments remain in place, so the database immediately diverges from the closure of the user's asserted facts. This is the core problem in #53.

The original framing of #53 asked: when an *inferred* relationship is deleted, which premise should also be retracted to keep the graph consistent? For inverses this is unambiguous. For multi-relation entailments — e.g. "delete this nibling row" implies *either* "this sibling premise is wrong" *or* "this parent premise is wrong" — there is no way for the system to know which.

A first proposal of mine introduced an `is_asserted` flag on `Relationship` to distinguish facts the user explicitly added from facts the engine inferred, with deletion only allowed on asserted rows. lucas42 rejected this on ethical grounds: the user's mental model treats all of a person's family members as equally real, and elevating asserted rows above inferred ones imposes a class hierarchy on family members that the user finds unacceptable. If A asserts cousin-of-B and the engine infers cousin-of-{B1, B2, B3, B4}, all five are equally cousins; the data model must not treat them otherwise.

The decision below is built on that constraint.

## Decision

Relationship deletion is governed by a single structural rule, supported by an explicit staging step.

### The closure-check rule

A staged set of rows can be deleted if and only if, after removing them, no row in the staged set would be re-inferred by the inference engine running over the remaining graph. Otherwise, deletion is refused.

This rule is stated as a property of the *staged set*, not of any single row. The staged set is what the system commits to delete atomically; the closure check decides whether that set is internally sufficient.

### Atomic deletion staging

Before the closure check runs, the system expands the user's deletion target into a staged set. Three expansions apply, in order:

1. **Inverse pairing.** For any row `(A, T, B)` in the staged set where T has an inverse T', add `(B, T', A)` if it exists. For symmetrical types (Sibling, HalfSibling, RomanticRelationship), add the mirror row `(B, T, A)`. This rule is unconditional — inverses and symmetrical mirrors are not separate facts in the user's model and are always deleted together.

2. **Sibling-group expansion** (offered, not automatic). When a closure check on the staged set fails *only* because of sibling-propagation rules — i.e. rows of the form `(A, T, Bi)` where Bi is in the sibling group of the row's object — the system computes the minimal extension that breaks the propagation: all `(A, T, Bj)` and their inverse/symmetrical mirrors for every Bj in the sibling group of the original target. The user is presented with a confirmation prompt naming the affected people (see *Refusal and confirmation UX* below). On confirmation, the extension is added to the staged set and the closure check runs again on the extended set.

3. **No further automatic expansion.** If the closure check still fails after sibling-group expansion (or fails for a reason other than sibling propagation), the deletion is refused. The user must manually retract one of the supporting facts and try again.

### Refusal and confirmation UX

Two distinct user-facing flows fall out of the rule, and they need different copy. Conflating them in a single message confuses the user.

**Refusal flow.** Deletion is structurally impossible without the user retracting a different row first. Example: deleting `A nibling B` while `B sibling C` and `C parent A` both remain. The system enumerates the supporting paths and shows them to the user with explicit re-routing instructions:

> This relationship can't be removed because it's implied by:
> – B is a sibling of C, and C is a parent of A.
>
> To remove it, first remove one of those relationships.

The supporting-path enumeration is bounded: walk the inference rules whose inferred output type is T, and for each rule `(rel1, rel2, T)`, list the matching `(A rel1 X, X rel2 B)` chains in the database. For inverse and transitive paths, include the corresponding chain (e.g. "B is a sibling of C, and C is a sibling of A"). All paths are shown; the user picks one to fix.

**Bulk-delete confirmation flow.** Deletion is possible but requires removing a set of related rows atomically because the relationship was sibling-propagated. Example: deleting `A cousin B` when A is also cousin of B's siblings B1..B4 by propagation. The system expands the staged set to all five and asks for confirmation, naming the affected people:

> Removing the cousin relationship with B also removes it from B's siblings: B1, B2, B3, B4. Remove all 5?

If the sibling group is large (8 or more), list the first 3–4 names followed by "and N others", with the full list available on demand.

The confirmation flow is *only* used for sibling-group expansion. Any other reason a deletion would be refused — multi-relation chains, transitive sibling chains where the user has not staged the whole transitive group — uses the refusal flow.

**No undo affordance.** A reversible undo (e.g. "Removed 5 cousin relationships. Undo?") was considered and rejected. The Django admin has no established undo pattern, the affordance would need to remain visible across navigation, and the deleted rows would need to be held in some recoverable state. A prompt-then-confirm gives the user the same protection with substantially less infrastructure.

### Half-sibling boundary

Converting a full-sibling relationship to a half-sibling relationship under the new rule may stalemate (deleting the full-sibling row could be refused because of transitive propagation, before the half-sibling can be added). A "downgrade" composite operation was considered and rejected on cost-vs-frequency grounds: full-sibling-to-half-sibling reclassifications are rare. The existing delete-then-add pattern is acceptable; users encountering a stalemate retract the supporting facts manually.

### One-time consistency audit

Before the closure-check rule is enabled in production, run a one-time audit pass that confirms the existing `Relationship` data is closed under the inference engine. Any rows that the engine would have created but which are missing from the database are added; any rows present in the database but which the engine considers extraneous (impossible under current rules) are flagged for inspection but not auto-deleted.

This is a one-shot migration, not an ongoing job. It guards against the new rule producing surprising refusals based on inferences that *should* exist in the data but don't, due to historical bugs or pre-engine imports.

### Loganne emission

A successful deletion (single-row, atomic-with-inverse, or bulk sibling-group) emits one Loganne `relationshipDeleted` event per row in the staged set, after the transaction commits. A refused deletion emits no event. This matches the existing per-row creation pattern; the bulk case generates multiple events because each row is a deletion in its own right.

## Alternatives considered

### Asserted-vs-inferred split (`is_asserted` flag)

Original proposal: tag each row as asserted (user-added) or inferred (engine-derived); only allow deletion on asserted rows; recompute the closure on every asserted-row deletion and prune any inferred rows no longer entailed. This resolves the multi-relation ambiguity by reframing it: there's no "delete a nibling" operation, only "retract one of the assertions that imply it."

Rejected because it imposes a hierarchy on family members. If A asserts cousin-of-B and the engine infers cousin-of-{B1..B4}, the asserted row is a different *class* than the inferred rows in the data model. The user's mental model — and ethical position — treats all five as equally real. Splitting them creates a silent hierarchy that surfaces in any UI, audit log, or admin view that shows the underlying flag, and would feel to the user like the system was deciding which family members were "real" and which were second-class. This is the wrong shape regardless of how clean the data model becomes.

### Cascade-only-the-easy-cases

A minimal version that cascades inverses on delete and does nothing about transitive or multi-relation propagation. Trivially implementable but does not solve the issue: inferred rows that depended on the deleted assertion stay around as orphans, and transitive sibling chains end up internally inconsistent. The graph would no longer be closed under inference, which is the property #53 needs.

### Negative-fact tombstones

Mark deleted rows as "asserted-not-true" so the inference engine refuses to re-create them. Conceptually a step toward RDF reification. Rejected because it does not resolve the multi-relation ambiguity (which premise was wrong?) and instead freezes a known-inconsistent graph in place. Strictly worse than the closure-check rule on every dimension.

### Silent atomic delete (Option 2 from the design discussion)

Instead of prompting before bulk-deleting a sibling group, delete all five rows silently and let the post-delete page reflect the new state. Considered briefly because it matches the "all five are equally cousins" mental model: deleting "this cousin relationship" obviously means the whole relationship.

Rejected on UX grounds. The Django admin's established pattern is to confirm before deleting things the user did not point at. A click on one row resulting in five rows disappearing — without any warning — violates that pattern. The relationships are equally real, but the *click* targeted one of them; the prompt acknowledges that gap without implying the rows have different status.

## Consequences

### Positive

- **Resolves #53 without imposing a hierarchy on relationships.** The closure check provides consistency without distinguishing asserted from inferred rows. All family members remain equally real in the data model.
- **The multi-relation ambiguity disappears by construction.** The system never has to guess which premise was wrong, because it doesn't try; refused-deletion UX hands the choice back to the user with full context.
- **Inverse and transitive cases are handled uniformly.** They are not special cases — atomic-staging and the closure check absorb them.
- **Database invariant is strengthened.** After this change, the relationship graph is always closed under inference. This is a one-line property worth being explicit about: it makes future debugging easier, and it makes the inference engine's behaviour predictable from any starting state.

### Negative

- **Implementation is non-trivial.** The closure check requires running the inference engine on a hypothetical post-deletion state — either by simulating the deletion in a transaction and rolling back, or by re-implementing the inference rules as pure functions that operate on a candidate graph snapshot. Both approaches are tractable at current data scale; the cost is engineering care, not algorithmic difficulty.
- **Refusal UX requires supporting-path enumeration.** The system must list the inference paths supporting a row. The enumeration logic is bounded (walk the rules whose inferred output is T) but adds new code surface. For users to act on a refusal, the enumeration must be readable in family-relationship terms ("B is a sibling of C, and C is a parent of A"), not raw row-tuples.
- **Sibling-group bulk-delete is a new kind of operation.** It needs its own admin URL, view, confirmation template, and Loganne emissions for each row. Modest scope, but new surface.
- **Performance.** The closure recompute on every delete attempt is O(rows-touched-by-the-affected-relationship-types). At current scale (low hundreds of rows estate-wide), negligible. Worth flagging if the dataset grows substantially.
- **One-time audit as a prerequisite.** The closure-check rule will produce confusing refusals if the existing data isn't already closed under inference. The audit step must run before the rule is enabled, and any flagged extraneous rows need manual review. This is a one-shot cost, not ongoing.
- **Stalemate cases still exist for some user intents.** Reclassifying a full sibling as a half-sibling, or untangling transitive sibling chains where the user wants to remove only some links, may require multiple manual retractions in a specific order. Documented; accepted as the cost of preserving the equal-treatment principle.

## Implementation notes (non-normative)

For the implementing developer:

- The closure check is most cleanly implemented as a transaction that performs the staged deletes, then queries the inference engine to see if any of the deleted rows would be re-created, then commits or rolls back accordingly. Django's `transaction.atomic` and `savepoint_rollback` are the natural primitives.
- Supporting-path enumeration lives next to `inferRelationships()` in `agents/models/relationship.py` — same rule set, queried for the inverse direction. Keep the rule set as the single source of truth.
- The bulk-delete-confirm view is a new admin URL, not an override of the standard `delete_selected` action. Keep the existing single-row delete path as the entry point; route to the bulk confirm when the closure check fails for sibling-propagation reasons specifically.
- Loganne events fire after `transaction.commit`, not inside the transaction itself, to avoid emitting on rolled-back deletions.
- The one-time audit can live as a one-off Django management command (`python manage.py audit_relationship_closure`). It does not need to ship as part of the main migration.
