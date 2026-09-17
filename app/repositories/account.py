from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account


def create_account(
    db: Session,
    user_id: int,
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
    account_id: int,
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


def get_accounts_by_user_id(
    db: Session,
    user_id: int,
) -> list[Account]:
    statement = select(Account).where(
        Account.user_id == user_id
    )

    return list(db.scalars(statement).all())
