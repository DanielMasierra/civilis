"""
LexJal — Conexión a base de datos
Sesiones asíncronas con SQLAlchemy 2.0.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from backend.config import get_settings

settings = get_settings()

# Motor asíncrono (reemplaza postgresql:// por postgresql+asyncpg://)
_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(
    _url,
    echo=settings.environment == "development",
    poolclass=NullPool,  # Mejor para contenedores
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """Dependencia FastAPI para obtener sesión de DB."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables():
    """Crea todas las tablas al iniciar la app (solo para dev; en prod usar Alembic)."""
    from backend.db.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
