from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.dependencies import get_db
from app.models import User
from app.repositories.account import (
    get_account_by_number,
    get_accounts_by_user_id,
)
from app.repositories.transfer import (
    get_transfer_by_id,
    get_transfers_by_account_ids,
)
from app.schemas.transfer import (
    TransferCreate,
    TransferHistoryResponse,
    TransferResponse,
)
from app.services.transfer import transfer


router = APIRouter(
    prefix="/transfers",
    tags=["Transfers"],
)


@router.post(
    "",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_transfer(
    transfer_data: TransferCreate,
    idempotency_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    accounts = get_accounts_by_user_id(
        db=db,
        user_id=current_user.id,
    )

    if not accounts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sender account not found.",
        )

    sender = accounts[0]

    receiver = get_account_by_number(
        db=db,
        account_number=transfer_data.receiver_account_number,
    )

    if receiver is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receiver account not found.",
        )

    try:
        transfer_record = transfer(
            db=db,
            user_id=current_user.id,
            idempotency_key=idempotency_key,
            sender_account_number=sender.account_number,
            receiver_account_number=receiver.account_number,
            amount=transfer_data.amount,
            currency=sender.currency,
            note=transfer_data.note,
        )

    except ValueError as error:
        message = str(error)

        if "not found" in message.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message,
            ) from error

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        ) from error

    return transfer_record


@router.get(
    "",
    response_model=TransferHistoryResponse,
)
def get_my_transfers(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    accounts = get_accounts_by_user_id(
        db=db,
        user_id=current_user.id,
    )

    account_ids = [
        account.id
        for account in accounts
    ]

    transfers, total = get_transfers_by_account_ids(
        db=db,
        account_ids=account_ids,
        limit=limit,
        offset=offset,
    )

    return TransferHistoryResponse(
        items=transfers,
        total=total,
        limit=limit,
        offset=offset,
    )

@router.get(
    "/{transfer_id}",
    response_model=TransferResponse,
)
def get_my_transfer(
    transfer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transfer_record = get_transfer_by_id(
        db=db,
        transfer_id=transfer_id,
    )

    if transfer_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transfer not found.",
        )

    user_account_ids = {
        account.id
        for account in get_accounts_by_user_id(
            db=db,
            user_id=current_user.id,
        )
    }

    if (
        transfer_record.sender_account_id not in user_account_ids
        and transfer_record.receiver_account_id not in user_account_ids
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this transfer.",
        )

    return transfer_record