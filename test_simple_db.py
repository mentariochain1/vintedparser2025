#!/usr/bin/env python3
"""Simple database connection test using asyncpg directly."""

import asyncio
import logging
import os
from dotenv import load_dotenv
import asyncpg

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_direct_connection():
    """Test database connection using asyncpg directly."""
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        logger.error("DATABASE_URL not found in environment")
        return False
    
    # Parse the URL to get connection parameters
    from urllib.parse import urlparse
    parsed = urlparse(database_url)
    
    logger.info(f"Testing direct connection to: {parsed.hostname}:{parsed.port}")
    
    try:
        # Connect directly with asyncpg
        conn = await asyncpg.connect(
            host=parsed.hostname,
            port=parsed.port,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path.lstrip('/'),
            statement_cache_size=0,  # Disable prepared statements
            server_settings={
                'application_name': 'vinted-parser-test'
            }
        )
        
        # Test query
        result = await conn.fetchrow("SELECT 1 as test, NOW() as current_time")
        logger.info(f"Connection successful! Result: {result}")
        
        # Test a simple table query
        try:
            tables = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public' LIMIT 5")
            logger.info(f"Found {len(tables)} tables in public schema")
        except Exception as e:
            logger.info(f"Table query failed (expected if no tables): {e}")
        
        await conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Connection failed: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_direct_connection())
    if success:
        print("✅ Direct database connection successful!")
    else:
        print("❌ Direct database connection failed!")