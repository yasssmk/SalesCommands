# backend/tests/territories/_builders.py
"""Shared data builders for territory-count tests."""

from app_modules.accounts.models import CompanyAccount, AccountClassification
from app_modules.contacts.models import Contact
from app_modules.territories.models import Territory


def mk_user(email, ca, role):
    from end_users.models import User
    return User.objects.create(
        email=email, client_account=ca, role=role, is_active=True,
    )


def mk_account(name, owner, ca, classification=AccountClassification.SMB,
               company_size=None):
    acc = CompanyAccount(
        company_name=name, has_buying_decision=True,
        account_owner=owner, classification=classification,
        company_size=company_size,
    )
    acc.save(user=owner, client_id=ca.id)
    return acc


def mk_contact(account, owner, ca, first_name='Jane', last_name='Doe',
               influence_level='UNKNOWN', has_buying_authority=None,
               opted_out=False):
    c = Contact(
        account=account, first_name=first_name, last_name=last_name,
        influence_level=influence_level, has_buying_authority=has_buying_authority,
        opted_out=opted_out,
    )
    c.save(user=owner, client_id=ca.id)
    return c


_seq = {'n': 0}


def mk_territory(owner, ca, filter_definition, ttype='ACCOUNT'):
    _seq['n'] += 1
    t = Territory(
        name=f'T{_seq["n"]}', type=ttype, owner=owner,
        filter_definition=filter_definition,
    )
    t.save(user=owner, client_id=ca.id)
    return t
