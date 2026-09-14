# Database lifecycle: create the async engine and provide one database session per request.
# create db engine
# create db sessions
# create db dependency

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# tells us what database to connect to (in our case postgressql) and manages the connection pool
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

# manages the connections . manages sql alchemy orm workflow. async_session maker is a factory which makes those db sessions
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# for orm operations. create one session per request.
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession for one request and close it afterward.

    Roll back pending changes if request handling raises an exception.
    Successful requests are not committed automatically; callers own commits.
    """
    async with AsyncSessionLocal() as db:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise
