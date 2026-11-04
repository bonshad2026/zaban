import argparse
from datetime import timedelta

from zaban.db import Base, SessionLocal, engine
from zaban.models import Guardian, Tenant, utcnow
from zaban.security import generate_api_key, hash_api_key
from zaban.services.passwords import hash_password


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
    with SessionLocal() as db:
        tenant = db.query(Tenant).filter(Tenant.status == "active").order_by(Tenant.created_at).first()
        if tenant is None:
            raise SystemExit("No active tenant. Create one first with the 'tenant' command.")
        email = args.email.strip().lower()
        if db.query(Guardian).filter(Guardian.email == email).first():
            raise SystemExit(f"A parent with the email {email} already exists.")
        db.add(
            Guardian(
                tenant_id=tenant.id,
                email=email,
                full_name=args.name.strip(),
                password_hash=hash_password(args.password),
            )
        )
        db.commit()
    print(f"Parent account created for {email}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="zaban administration")
    commands = parser.add_subparsers(dest="command", required=True)

    tenant = commands.add_parser("tenant", help="Create a tenant and print its API key once")
    tenant.add_argument("name", help="Tenant name, for example the customer's site name")
    tenant.add_argument("--quota", type=int, required=True, help="Token quota for the tenant")
    tenant.add_argument("--days", type=int, default=None, help="Days until the subscription expires")
    tenant.set_defaults(handler=_create_tenant)

    parent = commands.add_parser("parent", help="Create a parent account for the website")
    parent.add_argument("--email", required=True)
    parent.add_argument("--name", required=True, help="Full name shown in the website")
    parent.add_argument("--password", required=True, help="Initial password (change it after first sign-in)")
    parent.set_defaults(handler=_create_parent)

    args = parser.parse_args()
    Base.metadata.create_all(engine)
    args.handler(args)


if __name__ == "__main__":
    main()
