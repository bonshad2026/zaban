import uuid

from zaban.db import SessionLocal
from zaban.models import Guardian, Tenant, utcnow
from zaban.services.referrals import ALPHABET, CODE_LENGTH, new_code, referral_summary


def test_codes_are_six_readable_characters_and_unique(client):
    with SessionLocal() as db:
        codes = {new_code(db) for _ in range(50)}
        assert len(codes) == 50
        for code in codes:
            assert len(code) == CODE_LENGTH and set(code) <= set(ALPHABET)


def test_referral_summary_lists_names_and_counts_only(client):
    with SessionLocal() as db:
        tenant = db.query(Tenant).first()
        owner = Guardian(tenant_id=tenant.id, phone=f"0999{uuid.uuid4().int % 10**7:07d}", full_name="Owner Person",
                         referral_code=new_code(db), created_at=utcnow())
        db.add(owner)
        db.commit()
        invited = Guardian(tenant_id=tenant.id, phone=f"0998{uuid.uuid4().int % 10**7:07d}", full_name="Invited Person",
                           referred_by_id=owner.id, created_at=utcnow())
        db.add(invited)
        db.commit()
        summary = referral_summary(db, owner)
        assert summary["total"] == 1 and summary["with_plan"] == 0
        assert summary["people"] == [{"name": "Invited Person"}]
        assert set(summary["people"][0]) == {"name"}
