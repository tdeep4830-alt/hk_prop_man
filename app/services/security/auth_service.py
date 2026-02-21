"""Authentication and quota business logic."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.security import hash_password, verify_password
from app.models.audit import UsageQuota
from app.models.user import MembershipTier, User, UserIdentity


async def register_user(
    email: str,
    password: str,
    pref_lang: str,
    db: AsyncSession,
) -> User:
    """Create a new user with an email identity."""
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none() is not None:
        raise AppException(409, "auth.email_exists")

    user = User(
        email=email,
        hashed_password=hash_password(password),
        pref_lang=pref_lang,
    )
    db.add(user)
    await db.flush()  # populate user.id

    identity = UserIdentity(
        user_id=user.id,
        provider="email",
        provider_uid=email,
    )
    db.add(identity)
    return user


async def authenticate_user(
    email: str,
    password: str,
    db: AsyncSession,
) -> User:
    """Verify credentials and return the user, or raise."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.hashed_password):
        raise AppException(401, "auth.invalid_credentials")

    return user


# ---------------------------------------------------------------------------
# Quota management
# ---------------------------------------------------------------------------
def _get_daily_limit(tier: MembershipTier) -> int:
    """Return the daily LLM call limit for a membership tier. -1 = unlimited."""
    return settings.QUOTA_LIMITS.get(tier.value, 10)


async def check_quota(user: User, db: AsyncSession) -> None:
    """Raise AppException(429) if the user has exhausted today's quota."""
    limit = _get_daily_limit(user.membership_tier)
    if limit == -1:
        return  # unlimited

    quota = await _get_or_create_today_quota(user.id, db)
    if quota.llm_calls_count >= limit:
        raise AppException(429, "auth.quota_exceeded", limit=limit)


async def increment_usage(user_id, db: AsyncSession) -> None:
    """Increment today's LLM call count by 1."""
    quota = await _get_or_create_today_quota(user_id, db)
    quota.llm_calls_count += 1


async def _get_or_create_today_quota(user_id, db: AsyncSession) -> UsageQuota:
    today = date.today()
    result = await db.execute(
        select(UsageQuota).where(
            UsageQuota.user_id == user_id,
            UsageQuota.quota_date == today,
        )
    )
    quota = result.scalar_one_or_none()
    if quota is None:
        quota = UsageQuota(user_id=user_id, quota_date=today, llm_calls_count=0)
        db.add(quota)
        await db.flush()
    return quota
