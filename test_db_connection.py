#!/usr/bin/env python3
"""
Test database connectivity to diagnose connection issues.
"""

import asyncio
import sys
import os
from urllib.parse import urlparse

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config import settings

async def test_asyncpg_connection():
    """Test direct asyncpg connection."""
    print("🔌 Testing asyncpg connection...")
    
    try:
        import asyncpg
        
        # Parse the DATABASE_URL
        parsed = urlparse(settings.database_url)
        
        connection_params = {
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'user': parsed.username,
            'password': parsed.password,
            'database': parsed.path.lstrip('/') if parsed.path else 'postgres',
        }
        
        print(f"  Host: {connection_params['host']}")
        print(f"  Port: {connection_params['port']}")
        print(f"  Database: {connection_params['database']}")
        print(f"  User: {connection_params['user']}")
        
        # Test single connection
        conn = await asyncpg.connect(**connection_params)
        result = await conn.fetchrow("SELECT 1 as test, NOW() as current_time")
        await conn.close()
        
        print(f"✅ Direct connection successful: {result}")
        return True
        
    except Exception as e:
        print(f"❌ Direct connection failed: {e}")
        return False

async def test_connection_pool():
    """Test connection pool creation."""
    print("\n🏊 Testing connection pool...")
    
    try:
        import asyncpg
        from urllib.parse import urlparse
        
        parsed = urlparse(settings.database_url)
        connection_params = {
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'user': parsed.username,
            'password': parsed.password,
            'database': parsed.path.lstrip('/') if parsed.path else 'postgres',
            'statement_cache_size': 0,
            'server_settings': {
                'application_name': 'vinted-parser-test'
            }
        }
        
        # Create small pool
        pool = await asyncpg.create_pool(
            min_size=1,
            max_size=2,
            command_timeout=10,
            **connection_params
        )
        
        # Test pool
        async with pool.acquire() as conn:
            result = await conn.fetchrow("SELECT 1 as test")
            print(f"✅ Pool connection successful: {result}")
        
        await pool.close()
        return True
        
    except Exception as e:
        print(f"❌ Pool connection failed: {e}")
        return False

async def test_sqlalchemy_connection():
    """Test SQLAlchemy connection."""
    print("\n🔧 Testing SQLAlchemy connection...")
    
    try:
        from db.base import init_database, close_database
        
        await init_database()
        print("✅ SQLAlchemy initialization successful")
        
        await close_database()
        print("✅ SQLAlchemy cleanup successful")
        return True
        
    except Exception as e:
        print(f"❌ SQLAlchemy failed: {e}")
        return False

async def main():
    """Main test function."""
    print("🧪 Database Connection Diagnostics\n")
    
    # Check configuration
    print("📋 Configuration:")
    print(f"  DATABASE_URL: {settings.database_url[:50]}...")
    print(f"  SUPABASE_URL: {settings.supabase_url}")
    print(f"  Debug mode: {settings.debug}")
    print()
    
    # Test connections
    results = []
    
    # Test 1: Direct asyncpg
    results.append(await test_asyncpg_connection())
    
    # Test 2: Connection pool
    results.append(await test_connection_pool())
    
    # Test 3: SQLAlchemy
    results.append(await test_sqlalchemy_connection())
    
    # Summary
    print(f"\n📊 Results: {sum(results)}/3 tests passed")
    
    if all(results):
        print("🎉 All database connections working!")
        return True
    else:
        print("💥 Some database connections failed!")
        print("\n🔧 Troubleshooting tips:")
        print("1. Check if Supabase project is active")
        print("2. Verify database password in .env file")
        print("3. Check connection limits in Supabase dashboard")
        print("4. Try restarting Supabase project if on free tier")
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⏹ Test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)