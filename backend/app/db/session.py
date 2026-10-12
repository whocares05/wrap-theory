from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings


class Database:
    def __init__(self, settings: Settings) -> None:
        url = settings.async_database_url
        connect_args = (
            {"statement_cache_size": 0, "prepared_statement_cache_size": 0}
            if "pooler.supabase.com" in url
            else {}
        )
        self.engine: AsyncEngine = create_async_engine(
            url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=10,
            pool_recycle=300,
            connect_args=connect_args,
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessions() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    async def close(self) -> None:
        await self.engine.dispose()
