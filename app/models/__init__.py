"""All SQLAlchemy models — imported here so Alembic can discover them."""

from app.models.audit import AuditLog, UsageQuota  # noqa: F401
from app.models.chat import Conversation, Message  # noqa: F401
from app.models.knowledge import ChildChunk, ParentDoc  # noqa: F401
from app.models.user import User, UserIdentity  # noqa: F401
