from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from db.models import Base

class DBConnector:
    def __init__(self, database_url: str) -> None:
        self._engine = create_async_engine(database_url, echo=False)
        self._session_factory = async_sessionmaker(
            self._engine, expire_on_commit=False, class_=AsyncSession
        )

    def session(self) -> AsyncSession:
        return self._session_factory()

    async def create_tables(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)