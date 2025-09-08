"""Direct asyncpg adapter for Supabase transaction pooler compatibility."""

import logging
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any, Dict, List, Optional
from urllib.parse import urlparse
import asyncpg

from src.config import settings

logger = logging.getLogger(__name__)

class AsyncpgAdapter:
    """Direct asyncpg connection adapter for transaction pooler compatibility."""
    
    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None
        self._connection_params = self._parse_database_url()
    
    def _parse_database_url(self) -> Dict[str, Any]:
        """Parse DATABASE_URL into connection parameters."""
        database_url = settings.database_url
        parsed = urlparse(database_url)
        
        return {
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'user': parsed.username,
            'password': parsed.password,
            'database': parsed.path.lstrip('/') if parsed.path else 'postgres',
            'statement_cache_size': 0,  # Disable prepared statements
            'server_settings': {
                'application_name': 'vinted-parser-bot'
            }
        }
    
    async def initialize(self) -> None:
        """Initialize the connection pool."""
        try:
            logger.info(f"Creating asyncpg pool for {self._connection_params['host']}:{self._connection_params['port']}")
            
            self._pool = await asyncpg.create_pool(
                min_size=1,
                max_size=5,
                command_timeout=30,
                **self._connection_params
            )
            
            # Test the connection
            async with self._pool.acquire() as conn:
                result = await conn.fetchrow("SELECT 1 as test")
                logger.info(f"Database pool initialized successfully: {result}")
                
        except Exception as e:
            logger.error(f"Failed to initialize asyncpg pool: {e}")
            raise
    
    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("Database pool closed")
    
    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Get a database connection from the pool."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self._pool.acquire() as conn:
            yield conn
    
    async def execute(self, query: str, *args) -> str:
        """Execute a query and return the result."""
        async with self.get_connection() as conn:
            return await conn.execute(query, *args)
    
    async def fetch(self, query: str, *args) -> List[asyncpg.Record]:
        """Fetch multiple rows."""
        async with self.get_connection() as conn:
            return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        """Fetch a single row."""
        async with self.get_connection() as conn:
            return await conn.fetchrow(query, *args)
    
    async def fetchval(self, query: str, *args) -> Any:
        """Fetch a single value."""
        async with self.get_connection() as conn:
            return await conn.fetchval(query, *args)
    
    async def health_check(self) -> Dict[str, str]:
        """Perform database health check."""
        try:
            async with self.get_connection() as conn:
                result = await conn.fetchrow("SELECT 1 as health_check, NOW() as current_time")
                
                if result and result['health_check'] == 1:
                    return {
                        "status": "healthy",
                        "database": "connected",
                        "timestamp": str(result['current_time'])
                    }
                else:
                    return {"status": "unhealthy", "database": "query_failed"}
                    
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {"status": "unhealthy", "database": f"error: {str(e)}"}

# Global adapter instance
db_adapter = AsyncpgAdapter()

async def init_asyncpg_database() -> None:
    """Initialize the asyncpg database adapter."""
    await db_adapter.initialize()

async def close_asyncpg_database() -> None:
    """Close the asyncpg database adapter."""
    await db_adapter.close()

@asynccontextmanager
async def get_asyncpg_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Get an asyncpg database connection."""
    async with db_adapter.get_connection() as conn:
        yield conn