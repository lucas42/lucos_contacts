# 3. Primary email address per person

- **Status:** Proposed
- **Date:** 2026-07-08
- **Deciders:** lucas42 (owner), lucos-architect, lucos-ux
- **Related:** lucas42/lucos_aithne#298 (origin + decision thread); lucas42/lucos_contacts#764 (shared radio-select widget for name + email, lucos-ux); `lucos_aithne` OIDC consumer (emits the `email` claim)

## Context

`lucos_aithne` is a minimal-identity OIDC provider: it mints no identities and sources a person's identity attributes from `lucos_contacts` (keyed by contact ID). It advertises the OIDC `email` scope but emits **no** `email` claim, because a person can have several email addresses in contacts and there was no way to say which one is canonical. This blocks any relying party that requires an email — concretely, BookStack (`lucos_worlds`), whose OIDC flow **unconditionally** requires an email with no config to disable it, so worlds.l42.eu login fails at the final step (lucas42/lucos_aithne#298).

`lucos_contacts` already models multiple email addresses per person (`EmailAddress`, with an `active` flag) and already serialises the active set as an `email` array. What it lacks is a **primary** designation. lucas42's decision (lucas42/lucos_aithne#298): the primary email belongs in `lucos_contacts` (the data owner), designated per person, made available estate-wide; and `lucos_aithne` may release it to relying parties, gated on the OIDC `email` scope.

There is an established precedent to mirror: **`PersonName.is_primary`** (`app/agents/models/agent.py`) already implements "one primary among a person's rows" for names — a boolean flag, with `save()` enforcing the invariant (auto-designate the first as primary; unset the others when one is set) and denormalising the primary onto `Person._name` for cheap reads via `getName()`.

The designation mechanism was chosen (Option A) after a joint architect + UX assessment of three options; the alternatives (a `Person → EmailAddress` FK, or a generalised flag on the abstract `BaseAccount`) are recorded under *Alternatives considered*.

## Decision

### 1. `EmailAddress.is_primary` — mirror the `PersonName` pattern

Add `is_primary = BooleanField(default=False)` to `EmailAddress`, with `save()` logic mirroring `PersonName`:
- If the person has no active primary email, designate this one (auto-first).
- When one is set primary, unset `is_primary` on the person's other email rows (**unset-others-then-set**, so at no point do two rows hold it).
- The primary is always one of the person's own rows (criterion 1: the primary is by construction a member of the `email` list — it *is* an `EmailAddress` row, not a pointer).

### 2. Invariant: at most one **active** primary per person

- **`is_primary ⟹ active`.** `serializePerson` already filters the `email` array to *active* addresses, so an inactive row must never be the effective primary. Enforce this in `save()`/validation; if the primary email is deactivated, re-designate (or clear, leaving the person with no primary until one is chosen).
- **DB partial-unique constraint** — `UniqueConstraint(fields=['agent'], condition=Q(is_primary=True))` — as an integrity backstop *beneath* the model/admin logic, so the single-primary invariant holds even on non-`save()` write paths (bulk updates, future API writes). This is a strengthening over the `PersonName` precedent, which relies on `save()` alone. The unset-others-then-set ordering in §1 keeps a single save from momentarily creating two primaries and tripping the constraint. (Applies at `is_primary=True`, so zero-primary is allowed — a person with no active email simply has none.)

### 3. API: additive `primary_email` in `serializePerson`

Add a `primary_email` field to the person JSON (the person's active primary address, or `null`/absent if none). Keep the existing `email` array unchanged (non-breaking — consumers that want all active addresses keep it; consumers that want the canonical one use `primary_email`).

### 4. `lucos_aithne` consumer (scope-gated)

`lucos_aithne` parses `primary_email` from the `/people/{id}` response it already fetches and emits it as the OIDC `email` claim **when the `email` scope is requested** — in `/oauth2/userinfo` (sufficient for BookStack, which falls through to userinfo) and in the id_token (for robustness / RPs that don't call userinfo). If a person has no primary email, aithne omits the claim (the RP then reports a clear "no email" error until one is set). Tracked as a separate consumer change; needs the scope-gated-release sign-off lucas42 has already given.

### 5. Admin editing (rendering) is a separate, shared concern

Per lucas42, the *edit widget* — a mutually-exclusive single-select across the inline rows, applied to both `PersonName.is_primary` **and** `EmailAddress.is_primary` via a shared reusable abstraction — is factored out to lucas42/lucos_contacts#764 (lucos-ux), which is Blocked on this schema. A plain admin control is acceptable for this ADR's functional shipping; #764 delivers the "clearly one" UX (criterion 4) for name and email together.

## Consequences

### Positive
- A canonical primary email per person, owned by the data owner (`lucos_contacts`) and available to **every** contacts consumer, not just OIDC. Consistent with the existing `PersonName.is_primary` model pattern.
- Unblocks the OIDC `email` claim → BookStack/`lucos_worlds` login (the final blocker) and, downstream, lucas42/lucos_worlds#17.
- Stronger single-primary integrity than the name precedent (DB constraint, not just `save()`).

### Negative / trade-offs
- **Email adds complexity the name precedent doesn't have — the `active` flag.** "Primary among *active*" means deactivating the primary must re-designate or clear it; this is extra `save()`/validation logic beyond `PersonName`'s.
- **A new login-path dependency:** worlds.l42.eu login now depends on `lucos_contacts` availability *and* the person having an active primary email there (aithne's contacts lookup is best-effort; a contacts outage → no email claim → login fails from the RP's side). Worth a monitoring note (a contacts blip surfaces as "can't log into worlds").
- **Consistency debt with `PersonName`:** this ADR gives `EmailAddress` a DB constraint that `PersonName` lacks. Uniformity is desirable (lucas42 wants name + email treated the same). Recommend the shared-abstraction work (#764 and/or a follow-up) bring `PersonName` up to the same constraint; retrofitting it is **out of scope here** and needs a data check first (existing multi-primary names, if any).
- **Backfill:** existing people have emails but no `is_primary`. A data migration must designate one active primary per person (mirroring the auto-first rule — e.g. the oldest active address), correctable afterward via the admin.

## Alternatives considered
(Full joint architect + UX assessment on lucas42/lucos_aithne#298.)

- **`Person → EmailAddress` FK (`primary_email`).** Rejected. It gives *cardinality* (single-valued) but **not** membership — a bare FK can point at another person's row or an inactive one, needing the same validation `is_primary` needs anyway. It is also materially worse in django-admin against lucas42's criteria: the FK dropdown lists every `EmailAddress` estate-wide (needs per-instance scoping), and marking a brand-new inline email primary in the same save doesn't work cleanly (no PK yet at parent-form processing — the `RomanticRelationshipInline`/`personA` workaround), whereas the inline flag needs none of that.
- **Generalised `primary` on `BaseAccount`.** Rejected. `BaseAccount` is *abstract*, inherited by seven concrete models (email, postal, phone, and four Google/Facebook link/dedup records) — a field there lands on all seven, including records where "primary" is meaningless. A `PostalAddress.is_primary` can reuse this exact pattern later, independently, if/when actually wanted, with no coupling to this decision.

## Deferred work (tracked separately)
1. **`lucos_contacts` build** — the `EmailAddress.is_primary` field + `save()` logic + partial-unique constraint + `is_primary ⟹ active` + backfill migration + `primary_email` serialization.
2. **`lucos_aithne` consumer** — emit the scope-gated `email` claim (id_token + userinfo) from `primary_email`.
3. **Shared radio-select widget** for name + email — lucas42/lucos_contacts#764 (lucos-ux; Blocked on item 1).
4. **(Candidate)** bring `PersonName` up to the same DB single-primary constraint, as part of the shared abstraction — consistency; needs a data check.
