import secrets

from sqlalchemy.orm import Session as DBSession

from zaban.models import Guardian, Payment

# Six characters. Letters that look like digits (0, O, 1, I, L) are left out, so a code is easy to read aloud.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6


def new_code(db: DBSession) -> str:
    while True:
        code = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
        if db.query(Guardian.id).filter(Guardian.referral_code == code).first() is None:
            return code


def ensure_referral_codes(db: DBSession) -> None:
    # Adults who signed up before codes existed get one. Runs at startup.
    for guardian in db.query(Guardian).filter(Guardian.referral_code.is_(None)).all():
        guardian.referral_code = new_code(db)
    db.commit()


def referral_summary(db: DBSession, guardian: Guardian) -> dict:
    # Only the names of the people who joined with this code, and counts. Nothing else about them is shown.
    referred = db.query(Guardian).filter(Guardian.referred_by_id == guardian.id).order_by(Guardian.created_at).all()
    paid_ids = {
        row[0]
        for row in db.query(Payment.guardian_id).filter(Payment.guardian_id.in_([g.id for g in referred]), Payment.status == "confirmed").all()
    } if referred else set()
    return {
        "code": guardian.referral_code,
        "total": len(referred),
        "with_plan": len(paid_ids),
        "people": [{"name": g.full_name} for g in referred],
    }
