import secrets

from sqlalchemy.orm import Session

from app.db.models import Account


def generate_account_number(db: Session) -> str:
    while True:
        account_number = str(secrets.randbelow(9_000_000_000) + 1_000_000_000)

        existing = (
            db.query(Account)
            .filter(Account.account_number == account_number)
            .first()
        )

        if existing is None:
            return account_number