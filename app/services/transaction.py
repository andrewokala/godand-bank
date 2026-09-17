from sqlalchemy.orm import Session

from app.repositories.transaction import get_transactions_by_account_id


def get_account_transactions(
    db: Session,
    account_id: int,
):
    if account_id <= 0:
        raise ValueError("Account ID must be greater than zero.")

    return get_transactions_by_account_id(
        db=db,
        account_id=account_id,
    )