from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.auth import AuthRequest, SignupRequest
from app.services.auth_services import signup


router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)


@router.post(
    "/signup",
    response_model=AuthRequest,
    status_code=status.HTTP_201_CREATED,
)
def signup_endpoint(
    request: SignupRequest,
    db: Session = Depends(get_db),
):
    try:
        return signup(db, request)

    except ValueError as error:
        code = str(error)

        if code == "EMAIL_ALREADY_EXISTS":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": code,
                    "message": "Email is already in use.",
                    "field": "email",
                },
            )

        if code == "PHONE_ALREADY_EXISTS":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": code,
                    "message": "Phone is already in use.",
                    "field": "phone",
                },
            )

        if code == "TERMS_NOT_ACCEPTED":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": code,
                    "message": "Terms must be accepted.",
                    "field": "terms_accepted",
                },
            )

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "Validation failed.",
                "field": None,
            },
        )