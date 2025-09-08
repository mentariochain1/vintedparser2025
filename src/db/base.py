"""Database connection and session management."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy .ext .asyncio import AsyncEngine ,AsyncSession ,async_sessionmaker ,create_async_engine
from sqlalchemy .pool import NullPool

from src.config import settings

logger =logging .getLogger (__name__ )

_engine :AsyncEngine |None =None
_session_factory :async_sessionmaker [AsyncSession ]|None =None

def get_database_url() -> str:
    """Construct database URL from settings."""
    # Use DATABASE_URL if provided, otherwise construct from Supabase URL
    if hasattr(settings, 'database_url') and settings.database_url:
        logger.info("Using DATABASE_URL from settings")
        return settings.database_url
    
    # Fallback to local Postgres
    logger.warning("DATABASE_URL not found in settings, using local Postgres default")
    return "postgresql+asyncpg://postgres:postgres@localhost:5432/vinted_bot"

def create_engine() -> AsyncEngine:
    """Create async SQLAlchemy engine with connection pooling."""
    database_url = get_database_url()

    # Always disable statement cache for Supabase compatibility
    connect_args = {
        "server_settings": {
            "application_name": "vinted-parser-bot",
        },
        "command_timeout": 10,
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }
    
    logger.info("Disabled statement cache for Supabase transaction pooler compatibility")

    # Use NullPool to avoid connection reuse issues with pgbouncer
    engine = create_async_engine(
        database_url,
        poolclass=NullPool,  # Use NullPool for pgbouncer compatibility
        echo=settings.debug,
        connect_args=connect_args,
        # Disable SQLAlchemy's own statement preparation
        execution_options={
            "compiled_cache": {},
            "autocommit": False,
        },
    )

    logger.info("Database engine created successfully with NullPool")
    return engine

def get_engine ()->AsyncEngine :
    """Get or create the global database engine."""
    global _engine
    if _engine is None :
        _engine =create_engine ()
    return _engine

def get_session_factory ()->async_sessionmaker [AsyncSession ]:
    """Get or create the global session factory."""
    global _session_factory
    if _session_factory is None :
        engine =get_engine ()
        _session_factory =async_sessionmaker (
        engine ,
        class_ =AsyncSession ,
        expire_on_commit =False ,
        autoflush =True ,
        autocommit =False ,
        )
    return _session_factory

@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session with automatic cleanup."""
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    except Exception as e:
        # If SQLAlchemy fails, we'll use the asyncpg adapter
        logger.warning(f"SQLAlchemy session failed, falling back to asyncpg: {e}")
        from src.db.asyncpg_adapter import get_asyncpg_connection
        async with get_asyncpg_connection() as conn:
            yield conn

async def init_database() -> None:
    """Initialize database and ensure tables exist using SQLAlchemy models."""
    try:
        database_url = get_database_url()
        logger.info(f"Initializing database with URL: {database_url[:60]}...")
        
        # Create engine and ensure schema exists
        engine = get_engine()
        from src.db.models import Base
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database initialized and tables ensured")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

async def close_database ()->None :
    """Close database connections and cleanup resources."""
    global _engine ,_session_factory

    if _engine :
        await _engine .dispose ()
        _engine =None
        logger .info ("Database engine disposed")

    _session_factory =None

async def health_check ()->dict [str ,str ]:
    """Perform database health check."""
    try :
        engine =get_engine ()
        async with engine .begin ()as conn :
            from sqlalchemy import text
            result =await conn .execute (text("SELECT 1 as health_check"))
            row =result .fetchone ()

            if row and row [0 ]==1 :
                return {"status":"healthy","database":"connected"}
            else :
                return {"status":"unhealthy","database":"query_failed"}

    except Exception as e :
        logger .error (f"Database health check failed: {e }")
        return {"status":"unhealthy","database":f"error: {str (e )}"}

async def get_db ()->AsyncGenerator [AsyncSession ,None ]:
    """FastAPI dependency for database sessions."""
    async with get_db_session ()as session :
        yield session 