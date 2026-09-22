import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account


def generate_account_number(db: Session) -> str:
    while True:
        account_number = f"{secrets.randbelow(10_000_000_000):010d}"

        if get_account_by_number(
            db=db,
            account_number=account_number,
        ) is None:
            return account_number


def create_account(
    db: Session,
    user_id: uuid.UUID,
    account_number: str,
    currency: str = "NGN",
) -> Account:
    account = Account(
        user_id=user_id,
        account_number=account_number,
        currency=currency,
    )

    db.add(account)
    db.commit()
    db.refresh(account)

    return account


def get_account_by_id(
    db: Session,
    account_id: uuid.UUID,
) -> Account | None:
    statement = select(Account).where(Account.id == account_id)

    return db.scalar(statement)


def get_account_by_number(
    db: Session,
    account_number: str,
) -> Account | None:
    statement = select(Account).where(
        Account.account_number == account_number
    )

    return db.scalar(statement)


def get_account_by_number_for_update(
    db: Session,
    account_number: str,
) -> Account | None:
    statement = (
        select(Account)
        .where(Account.account_number == account_number)
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    return db.scalar(statement)


def get_accounts_by_user_id(
    db: Session,
    user_id: uuid.UUID,
) -> list[Account]:
    statement = select(Account).where(
        Account.user_id == user_id
    )

    return list(db.scalars(statement).all())
