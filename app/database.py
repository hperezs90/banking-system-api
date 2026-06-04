from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

# asyncpg usa 'ssl=require' en lugar de 'sslmode=require'
DATABASE_URL = (
    settings.database_url
    .replace("postgresql://", "postgresql+asyncpg://")
    .replace("sslmode=require", "ssl=require")
)

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.debug,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
