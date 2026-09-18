from app.db.session import SessionLocal
from app.repositories.user import (
    create_user,
    get_user_by_email,
    get_user_by_id,
)


def test_user_repository():
    db = SessionLocal()

    email = "repository@test.godandbank.local"

    try:
        user = create_user(
            db=db,
            full_name="Repository Test",
            email=email,
            phone="+2348012345003",
            password_hash="test_hash",
        )

        assert user.id is not None
        assert user.email == email

        saved_by_id = get_user_by_id(
            db=db,
            user_id=user.id,
        )

        assert saved_by_id is not None
        assert saved_by_id.email == email

        saved_by_email = get_user_by_email(
            db=db,
            email=email,
        )

        assert saved_by_email is not None
        assert saved_by_email.id == user.id

    finally:
        if "user" in locals() and user.id is not None:
            db.delete(user)
            db.commit()

        db.close()
