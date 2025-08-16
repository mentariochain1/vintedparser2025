#!/usr/bin/env python3
"""
Simple bot test script to verify functionality without full server startup.
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from bot.bot import create_bot, create_dispatcher
from config import settings

async def test_bot_creation():
    """Test bot creation and basic functionality."""
    print("🤖 Testing bot creation...")
    
    try:
        # Test bot creation
        bot = create_bot()
        print("✅ Bot created successfully")
        
        # Test dispatcher creation (fallback mode)
        dp = create_dispatcher(use_fallback=True)
        print("✅ Dispatcher created successfully (fallback mode)")
        
        # Test bot info
        bot_info = await bot.get_me()
        print(f"✅ Bot info: @{bot_info.username} ({bot_info.first_name})")
        
        # Close bot session
        await bot.session.close()
        print("✅ Bot session closed")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

async def main():
    """Main test function."""
    print("🧪 Starting bot functionality test...\n")
    
    # Check environment
    if not settings.bot_token:
        print("❌ BOT_TOKEN not found in environment")
        return False
    
    print(f"🔑 Bot token: {settings.bot_token[:10]}...")
    print(f"🌍 Environment: {'development' if settings.debug else 'production'}")
    print()
    
    # Test bot creation
    success = await test_bot_creation()
    
    if success:
        print("\n🎉 All tests passed! Bot is ready to use.")
        return True
    else:
        print("\n💥 Tests failed! Check configuration.")
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⏹ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)