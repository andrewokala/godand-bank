from datetime import UTC, datetime

import pytest

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import KYCStatus, User
from app.services.auth import authenticate_user, register_user


def test_register_user_creates_user_with_hashed_password():
    db = SessionLocal()

    email = "auth-register@test.godandbank.local"

    try:
        user = register_user(
            db=db,
            full_name="Auth Test User",
            email=email,
            phone="+2348012345010",
            password="TestPassword123!",
        )

        assert user.id is not None
        assert user.email == email
        assert user.full_name == "Auth Test User"
        assert user.password_hash != "TestPassword123!"
        assert user.terms_accepted_at is not None
        assert user.kyc_status == KYCStatus.PENDING

    finally:
        if "user" in locals() and user.id is not None:
            db.delete(user)
            db.commit()

        db.close()


def test_register_user_rejects_duplicate_email():
    db = SessionLocal()

    email = "auth-duplicate@test.godandbank.local"

    try:
        first_user = register_user(
            db=db,
            full_name="First User",
            email=email,
            phone="+2348012345011",
            password="TestPassword123!",
        )

        with pytest.raises(ValueError, match="Email is already registered."):
            register_user(
                db=db,
                full_name="Second User",
                email=email,
                phone="+2348012345012",
                password="TestPassword123!",
            )

    finally:
        if "first_user" in locals() and first_user.id is not None:
            db.delete(first_user)
            db.commit()

        db.close()


def test_authenticate_user_accepts_correct_password():
    db = SessionLocal()

    email = "auth-login@test.godandbank.local"

    try:
        user = User(
            full_name="Login Test User",
            email=email,
            phone="+2348012345013",
            password_hash=hash_password("TestPassword123!"),
            kyc_status=KYCStatus.PENDING,
            terms_accepted_at=datetime.now(UTC),
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        result = authenticate_user(
            db=db,
            email=email,
            password="TestPassword123!",
        )

        assert result.id == user.id
        assert result.failed_login_count == 0
        assert result.locked_until is None

    finally:
        if "user" in locals() and user.id is not None:
            db.delete(user)
            db.commit()

        db.close()


def test_authenticate_user_rejects_wrong_password():
    db = SessionLocal()

    email = "auth-wrong-password@test.godandbank.local"

    try:
        user = User(
            full_name="Wrong Password User",
            email=email,
            phone="+2348012345014",
            password_hash=hash_password("TestPassword123!"),
            kyc_status=KYCStatus.PENDING,
            terms_accepted_at=datetime.now(UTC),
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        with pytest.raises(ValueError, match="Invalid email or password."):
            authenticate_user(
                db=db,
                email=email,
                password="WrongPassword123!",
            )

        db.refresh(user)

        assert user.failed_login_count == 1
        assert user.locked_until is None

    finally:
        if "user" in locals() and user.id is not None:
            db.delete(user)
            db.commit()

        db.close()

def test_authenticate_user_locks_after_five_failed_attempts():
    db = SessionLocal()

    email = "auth-lockout@test.godandbank.local"

    try:
        user = User(
            full_name="Lockout Test User",
            email=email,
            phone="+2348012345015",
            password_hash=hash_password("TestPassword123!"),
            kyc_status=KYCStatus.PENDING,
            terms_accepted_at=datetime.now(UTC),
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        for attempt in range(1, 6):
            with pytest.raises(
                ValueError,
                match="Invalid email or password.",
            ):
                authenticate_user(
                    db=db,
                    email=email,
                    password="WrongPassword123!",
                )

            db.refresh(user)

            assert user.failed_login_count == attempt

        assert user.failed_login_count == 5
        assert user.locked_until is not None

    finally:
        if "user" in locals() and user.id is not None:
            db.delete(user)
            db.commit()

        db.close()

def test_authenticate_user_rejects_locked_account():
    db = SessionLocal()

    email = "auth-locked@test.godandbank.local"

    try:
        user = User(
            full_name="Already Locked User",
            email=email,
            phone="+2348012345016",
            password_hash=hash_password("TestPassword123!"),
            kyc_status=KYCStatus.PENDING,
            terms_accepted_at=datetime.now(UTC),
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        for _ in range(5):
            with pytest.raises(
                ValueError,
                match="Invalid email or password.",
            ):
                authenticate_user(
                    db=db,
                    email=email,
                    password="WrongPassword123!",
                )

        db.refresh(user)

        assert user.locked_until is not None
        failed_count_before = user.failed_login_count

        with pytest.raises(
            ValueError,
            match="Account is temporarily locked.",
        ):
            authenticate_user(
                db=db,
                email=email,
                password="TestPassword123!",
            )

        db.refresh(user)

        assert user.failed_login_count == failed_count_before

    finally:
        if "user" in locals() and user.id is not None:
            db.delete(user)
            db.commit()

        db.close()

def test_authenticate_user_resets_failed_login_state_on_success():
    db = SessionLocal()

    email = "auth-reset@test.godandbank.local"

    try:
        user = User(
            full_name="Reset Test User",
            email=email,
            phone="+2348012345017",
            password_hash=hash_password("TestPassword123!"),
            kyc_status=KYCStatus.PENDING,
            terms_accepted_at=datetime.now(UTC),
            failed_login_count=3,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        result = authenticate_user(
            db=db,
            email=email,
            password="TestPassword123!",
        )

        db.refresh(user)

        assert result.id == user.id
        assert user.failed_login_count == 0
        assert user.locked_until is None

    finally:
        if "user" in locals() and user.id is not None:
            db.delete(user)
            db.commit()

        db.close()

def test_authenticate_user_rejects_rejected_kyc_status():
    db = SessionLocal()

    email = "auth-kyc-rejected@test.godandbank.local"

    try:
        user = User(
            full_name="Rejected KYC User",
            email=email,
            phone="+2348012345018",
            password_hash=hash_password("TestPassword123!"),
            kyc_status=KYCStatus.REJECTED,
            terms_accepted_at=datetime.now(UTC),
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        with pytest.raises(
            ValueError,
            match="Account KYC has been rejected.",
        ):
            authenticate_user(
                db=db,
                email=email,
                password="TestPassword123!",
            )

        db.refresh(user)

        assert user.failed_login_count == 0
        assert user.locked_until is None

    finally:
        if "user" in locals() and user.id is not None:
            db.delete(user)
            db.commit()

        db.close()