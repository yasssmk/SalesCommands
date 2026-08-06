"""
Data migration: normalize existing empty-string email / phone_number to NULL.

Root-cause cleanup for the unique-constraint collision on
(account, email, client_id): PostgreSQL treats '' as a value equal to itself,
so two contacts with email='' in the same account violate the constraint,
whereas multiple NULLs are allowed. The write path normalizes ''->NULL for
new/edited contacts, but rows already stored with '' must be cleaned once.

Scope is deliberately locked to email + phone_number. linkedin is intentionally
excluded: the audit established it carries no unique constraint, so its '' vs
NULL state cannot cause this collision.

Idempotent (re-running matches zero rows), tenant-neutral (''->NULL never
crosses client_id), and reversible as a documented no-op (see reverse_noop).
"""

from django.db import migrations


def normalize_empty_to_null(apps, schema_editor):
    """Convert email='' and phone_number='' to NULL via mass UPDATE (no save())."""
    Contact = apps.get_model('module_contacts', 'Contact')

    before_email = Contact.objects.filter(email='').count()
    before_phone = Contact.objects.filter(phone_number='').count()
    print(f"\n  before: email=''={before_email}, phone_number=''={before_phone}")

    updated_email = Contact.objects.filter(email='').update(email=None)
    updated_phone = Contact.objects.filter(phone_number='').update(phone_number=None)

    after_email = Contact.objects.filter(email='').count()
    after_phone = Contact.objects.filter(phone_number='').count()
    print(
        f"  updated: email {updated_email} -> NULL, phone_number {updated_phone} -> NULL"
    )
    print(f"  after:  email=''={after_email}, phone_number=''={after_phone}")


def reverse_noop(apps, schema_editor):
    """
    Intentional no-op.

    NULL->'' is ambiguous — we cannot tell which NULLs were originally '' — and,
    more importantly, we do NOT want to reintroduce empty strings that would
    recreate the exact collision this migration removes. Reversing therefore
    leaves the data as-is (the schema is unchanged), keeping the migration
    formally reversible without undoing the cleanup.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('module_contacts', '0002_remove_contact_module_cont_first_n_da6ea2_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(
            normalize_empty_to_null,
            reverse_code=reverse_noop,
        ),
    ]
