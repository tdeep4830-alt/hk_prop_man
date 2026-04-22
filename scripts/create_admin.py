"""Create or promote an admin (enterprise) user in Supabase.

Usage:
    python scripts/create_admin.py --email admin@example.com --password yourpassword

If the email already exists, the script promotes that account to enterprise tier.
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import MembershipTier, User, UserIdentity


async def create_or_promote_admin(email: str, password: str) -> None:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        connect_args={"statement_cache_size": 0},
    )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        async with db.begin():
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

            if user is None:
                user = User(
                    email=email,
                    hashed_password=hash_password(password),
                    membership_tier=MembershipTier.ENTERPRISE,
                    pref_lang="zh_hk",
                )
                db.add(user)
                await db.flush()

                identity = UserIdentity(
                    user_id=user.id,
                    provider="email",
                    provider_uid=email,
                )
                db.add(identity)
                print(f"[OK] Admin user created: {email}")
            else:
                user.membership_tier = MembershipTier.ENTERPRISE
                if password:
                    user.hashed_password = hash_password(password)
                print(f"[OK] Existing user promoted to enterprise: {email}")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create or promote an admin user")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", required=True, help="Admin password")
    args = parser.parse_args()

    asyncio.run(create_or_promote_admin(args.email, args.password))
