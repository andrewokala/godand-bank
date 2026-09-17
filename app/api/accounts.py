from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.repositories.account import (
    create_account,
    get_account_by_id,
)
from app.schemas.account import AccountCreate, AccountResponse

router = APIRouter(
    prefix="/accounts",
    tags=["Accounts"],
)


@router.post(
    "",
    response_model=AccountResponse,
    status_code=201,
)
def create_new_account(
    account_data: AccountCreate,
    db: Session = Depends(get_db),
):
    existing_account = get_account_by_id(
        db=db,
        account_id=0,
    )

    account = create_account(
        db=db,
        user_id=1,
        account_number=account_data.account_number,
        currency=account_data.currency,
    )

    return account


@router.get(
    "/{account_id}",
    response_model=AccountResponse,
)
def get_account(
    account_id: int,
    db: Session = Depends(get_db),
):
    account = get_account_by_id(
        db=db,
        account_id=account_id,
    )

    if account is None:
        raise HTTPException(
            status_code=404,
            detail="Account not found",
        )

    return account