from datetime import UTC, datetime
from uuid import uuid4

from app.db.session import SessionLocal
from app.models import AuditLog, KYCStatus, User
from app.repositories.audit_log import create_audit_log


def test_create_audit_log():
    db = SessionLocal()

    email = f"audit-{uuid4()}@godandbank.local"
    phone = f"+23480{uuid4().int % 10**9:09d}"

    try:
        user = User(
            full_name="Audit Test User",
            email=email,
            phone=phone,
            password_hash="test_hash",
            kyc_status=KYCStatus.VERIFIED,
            terms_accepted_at=datetime.now(UTC),
        )

        db.add(user)
        db.flush()

        audit_log = create_audit_log(
            db=db,
            actor_user_id=user.id,
            action="transfer.created",
            ip_address="127.0.0.1",
            metadata_json={
                "reference": "TRF-AUDIT-TEST",
                "amount": "100.00",
            },
        )

        db.commit()
        db.refresh(audit_log)

        assert audit_log.id is not None
        assert audit_log.actor_user_id == user.id
        assert audit_log.action == "transfer.created"
        assert str(audit_log.ip_address) == "127.0.0.1"
        assert audit_log.metadata_json["reference"] == "TRF-AUDIT-TEST"
        assert audit_log.metadata_json["amount"] == "100.00"

    finally:
        db.rollback()

        if "audit_log" in locals() and audit_log.id:
            db.query(AuditLog).filter(
                AuditLog.id == audit_log.id
            ).delete(synchronize_session=False)

        if "user" in locals() and user.id:
            db.query(User).filter(
                User.id == user.id
            ).delete(synchronize_session=False)

        db.commit()
        db.close()
