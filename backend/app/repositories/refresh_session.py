# Refresh-session database access: stage inserts and conditional revocations; AuthService owns commits.
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_session import RefreshSession


class RefreshSessionRepository:
    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        user_id,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshSession:
        """Stage a refresh session for user_id using a token hash and UTC expiry.

        Flush the insert and return the ORM object without committing. The
        caller must commit or roll back, allowing rotation to remain atomic.
        """
        refresh_session = RefreshSession(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        db.add(refresh_session)

        await db.flush()

        return refresh_session

    @staticmethod
    async def revoke(
        db: AsyncSession,
        token_hash: str,
        *,
        active_only: bool = False,
    ) -> RefreshSession | None:
        """Conditionally revoke a session matching token_hash and return it.

        Only rows with no revocation time can be updated. With active_only=True,
        also require an expiry in the future. Return None when no row qualifies.
        The conditional UPDATE prevents double consumption during rotation.
        This method never commits; the caller owns the transaction.
        """
        now = datetime.now(UTC)
        statement = update(RefreshSession).where(
            RefreshSession.token_hash == token_hash,
            RefreshSession.revoked_at.is_(None),
        )
        if active_only:
            statement = statement.where(RefreshSession.expires_at > now)
        result = await db.execute(
            statement.values(revoked_at=now).returning(RefreshSession)
        )
        return result.scalar_one_or_none()
