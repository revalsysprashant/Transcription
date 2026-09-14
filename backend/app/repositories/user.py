# User database access: look up Google identities or local UUIDs and persist new users.
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    @staticmethod
    async def get_by_google_id(
        db: AsyncSession,
        google_id: str,
    ) -> User | None:
        """Return the user matching Google’s stable subject ID, or None.

        Execute a read using db without committing the transaction.
        """
        result = await db.execute(
            select(User).where(
                User.google_id == google_id
            )
        )

        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        user_id: UUID,
    ) -> User | None:
        """Return the user matching the local UUID, or None, without committing."""
        result = await db.execute(
            select(User).where(
                User.id == user_id
            )
        )

        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        google_id: str,
        email: str,
        name: str | None,
        avatar_url: str | None,
    ) -> User:
        """Insert a Google-authenticated user and return the refreshed ORM object.

        Unlike refresh-session inserts, this method currently commits db itself.
        Optional name and avatar fields may be None.
        """
        user = User(
            google_id=google_id,
            email=email,
            name=name,
            avatar_url=avatar_url,
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        return user
