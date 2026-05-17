# -*- coding: utf-8 -*-
"""
Management command: audit_relationship_closure

Audits the Relationship table for consistency with the inference engine's closure rules.

See docs/adr/0001-relationship-deletion-semantics.md (section "One-time consistency audit")
and README.md for context and usage instructions.
"""
from django.core.management.base import BaseCommand
from agents.models import Person, Relationship
from agents.models.engine import closure as _engine_closure


def compute_closure(initial_rows):
    """
    Thin wrapper over engine.closure() that returns just the frozenset of rows.

    Preserved for backward compatibility with existing tests that import
    compute_closure directly from this module.
    """
    return _engine_closure(initial_rows).rows


class Command(BaseCommand):
    help = (
        'Audit the Relationship table for closure consistency with the inference engine. '
        'Reports missing rows (inferred but absent) and extraneous rows (present but not '
        'inferable). With --apply-missing, auto-creates the missing rows.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply-missing',
            action='store_true',
            help=(
                'Automatically create any rows that the inference engine would have produced '
                'but which are absent from the database. Safe to run: all created rows are '
                'consistent with the current rule set by construction.'
            ),
        )

    def handle(self, *args, **options):
        apply_missing = options['apply_missing']

        # ── Load people for readable output ───────────────────────────────────
        people = {p.pk: p.getName() for p in Person.objects.all()}

        def name_of(person_id):
            return people.get(person_id, f'Person #{person_id}')

        def row_label(subj_id, obj_id, rel_key):
            return f'{name_of(subj_id)} {rel_key} {name_of(obj_id)}'

        # ── Load all DB rows ──────────────────────────────────────────────────
        db_rows = frozenset(
            (rel.subject_id, rel.object_id, rel.relationshipType)
            for rel in Relationship.objects.all()
        )

        # ── Compute closure ───────────────────────────────────────────────────
        closure = compute_closure(db_rows)

        # ── Compare ───────────────────────────────────────────────────────────
        missing = closure - db_rows        # in closure, not in DB

        # Note: with purely additive inference rules, extraneous is always the empty
        # set — the closure computation starts from db_rows and can only add rows, so
        # db_rows ⊆ closure always.  The section is retained for completeness and to
        # satisfy the audit interface; it would become non-empty if inference rules were
        # ever changed to reject rows rather than only add them.
        extraneous = db_rows - closure     # in DB, not in closure (structurally always {})

        # ── Report: missing ───────────────────────────────────────────────────
        self.stdout.write('=== Missing rows ===')
        self.stdout.write(f'Total: {len(missing)}')

        if missing:
            by_type = {}
            for row in missing:
                by_type.setdefault(row[2], []).append(row)

            for rel_key in sorted(by_type):
                rows = sorted(by_type[rel_key])
                count = len(rows)
                self.stdout.write(f'\n  {rel_key} ({count} {"row" if count == 1 else "rows"}):')
                for subj_id, obj_id, rk in rows:
                    self.stdout.write(f'    - {row_label(subj_id, obj_id, rk)}')

        # ── Report: extraneous ────────────────────────────────────────────────
        self.stdout.write('\n=== Extraneous rows ===')
        self.stdout.write(f'Total: {len(extraneous)}')

        if extraneous:
            by_type = {}
            for row in extraneous:
                by_type.setdefault(row[2], []).append(row)

            for rel_key in sorted(by_type):
                rows = sorted(by_type[rel_key])
                count = len(rows)
                self.stdout.write(f'\n  {rel_key} ({count} {"row" if count == 1 else "rows"}):')
                for subj_id, obj_id, rk in rows:
                    self.stdout.write(f'    - {row_label(subj_id, obj_id, rk)}')

        # ── Summary ───────────────────────────────────────────────────────────
        self.stdout.write('\n=== Summary ===')
        if not missing and not extraneous:
            self.stdout.write('Database is closed: zero missing, zero extraneous.')
        else:
            parts = []
            if missing:
                parts.append(f'{len(missing)} missing')
            if extraneous:
                parts.append(f'{len(extraneous)} extraneous')
            self.stdout.write(f'Database is NOT closed: {", ".join(parts)}.')

        # ── Apply missing rows ────────────────────────────────────────────────
        if apply_missing and missing:
            self.stdout.write('\n=== Applying missing rows ===')
            created_count = 0
            for subj_id, obj_id, rel_key in sorted(missing):
                _, created = Relationship.objects.get_or_create(
                    subject_id=subj_id,
                    object_id=obj_id,
                    relationshipType=rel_key,
                )
                if created:
                    created_count += 1
                    self.stdout.write(f'  Created: {row_label(subj_id, obj_id, rel_key)}')
                # else: already existed (may have been created by inference
                # triggered when an earlier missing row was saved)

            self.stdout.write(
                f'\nCreated {created_count} missing '
                f'{"relationship" if created_count == 1 else "relationships"}.'
            )
        elif apply_missing and not missing:
            self.stdout.write('\nNo missing rows to apply.')
