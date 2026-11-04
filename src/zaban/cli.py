import argparse
from datetime import timedelta

from zaban.db import Base, SessionLocal, engine
from zaban.models import Guardian, Tenant, utcnow
from zaban.security import generate_api_key, hash_api_key
from zaban.services.otp import normalize_phone


def _create_tenant(args: argparse.Namespace) -> None:
    api_key = generate_api_key()
    expires_at = utcnow() + timedelta(days=args.days) if args.days else None
    with SessionLocal() as db:
        db.add(
            Tenant(
                name=args.name,
                api_key_hash=hash_api_key(api_key),
                quota_tokens=args.quota,
                expires_at=expires_at,
            )
        )
        db.commit()
    print(f"Tenant created: {args.name}")
    print(f"API key (shown once, store it securely): {api_key}")


def _create_parent(args: argparse.Namespace) -> None:
    phone = normalize_phone(args.phone)
    if phone is None:
        raise SystemExit("The mobile number must look like 09121234567.")
    with SessionLocal() as db:
        tenant = db.query(Tenant).filter(Tenant.status == "active").order_by(Tenant.created_at).first()
        if tenant is None:
            raise SystemExit("No active tenant. Create one first with the 'tenant' command.")
        if db.query(Guardian).filter(Guardian.phone == phone).first():
            raise SystemExit("An account with this mobile number already exists.")
        db.add(Guardian(tenant_id=tenant.id, phone=phone, full_name=args.name.strip()))
        db.commit()
    print("Adult account created. The person signs in with an SMS code sent to that number.")


def main() -> None:
    parser = argparse.ArgumentParser(description="zaban administration")
    commands = parser.add_subparsers(dest="command", required=True)

    tenant = commands.add_parser("tenant", help="Create a tenant and print its API key once")
    tenant.add_argument("name", help="Tenant name, for example the customer's site name")
    tenant.add_argument("--quota", type=int, required=True, help="Token quota for the tenant")
    tenant.add_argument("--days", type=int, default=None, help="Days until the subscription expires")
    tenant.set_defaults(handler=_create_tenant)

    parent = commands.add_parser("parent", help="Create an adult account that signs in with an SMS code")
    parent.add_argument("--phone", required=True, help="Mobile number, for example 09121234567")
    parent.add_argument("--name", required=True, help="Full name shown in the website")
    parent.set_defaults(handler=_create_parent)

    args = parser.parse_args()
    Base.metadata.create_all(engine)
    args.handler(args)


if __name__ == "__main__":
    main()
