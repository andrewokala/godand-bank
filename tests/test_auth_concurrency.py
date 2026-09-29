import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from app.db.session import SessionLocal
from app.models import User
from app.services.auth import authenticate_user
from app.core.security import hash_password


def test_concurrent_failed_logins_are_counted_correctly():
    db = SessionLocal()
    email = "auth-concurrency@test.godandbank.local"
    password = "CorrectPassword123!"

    try:
        user = User(
            full_name="Auth Concurrency Test",
            email=email,
            phone="+2348012345999",
            password_hash=hash_password(password),
            terms_accepted_at=datetime.now(UTC),
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        # Make the test user eligible for five failed attempts.
        user.failed_login_count = 0
        user.locked_until = None
        db.commit()

        barrier = threading.Barrier(5)

        def attempt_login():
            worker_db = SessionLocal()

            try:
                barrier.wait()

                try:
                    authenticate_user(
                        db=worker_db,
                        email=email,
                        password="WrongPassword123!",
                    )
                except ValueError as error:
                    return str(error)

            finally:
                worker_db.close()

        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(lambda _: attempt_login(), range(5)))

        db.expire_all()
        saved_user = db.query(User).filter(User.email == email).first()

        assert all(result == "Invalid email or password." for result in results)
        assert saved_user is not None
        assert saved_user.failed_login_count == 5
        assert saved_user.locked_until is not None

    finally:
        if "user" in locals() and user.id is not None:
            db.delete(user)
            db.commit()

        db.close()