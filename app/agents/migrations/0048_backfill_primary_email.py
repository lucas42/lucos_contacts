from django.db import migrations


# Designate one active primary email per person who has active emails but no
# primary among them yet (auto-first: the oldest active address, i.e. lowest pk,
# mirroring the existing PersonName auto-first rule).
def backfill_primary_email(apps, schema_editor):
    Person = apps.get_model('agents', 'Person')
    EmailAddress = apps.get_model('agents', 'EmailAddress')
    for person in Person.objects.all():
        activeEmails = EmailAddress.objects.filter(agent=person, active=True).order_by('pk')
        if not activeEmails.filter(is_primary=True).exists():
            firstEmail = activeEmails.first()
            if firstEmail is not None:
                firstEmail.is_primary = True
                firstEmail.save()


# No-op: unsetting is_primary again is a safe, non-destructive reversal - the
# field itself is removed by reversing the preceding schema migration.
def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0047_emailaddress_is_primary_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_primary_email, noop_reverse),
    ]
