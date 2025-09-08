#!/usr/bin/env python3
"""
Demonstration of how images are embedded directly in Telegram messages without downloading.
This shows the actual code flow used by the bot.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.bot.services.image import create_telegram_media_group
from aiogram.types import InputMediaPhoto

async def demo_image_embedding():
    """Demonstrate how the bot embeds image URLs directly in messages."""

    # Sample image URLs extracted from Vinted (from our test)
    sample_image_urls = [
        "https://images1.vinted.net/t/04_01a6a_E9WbNz1AjNAYYucp2KuHMaGt/f800/1757241153.webp?s=15005302e34ad8a0946451cff73483ecdd3fcfa2",
        "https://images1.vinted.net/t/04_005a3_QxkZNjDspD8dMG4p9o1pYCFk/f800/1736083012.webp?s=16472633874eeebcaea8c262fd346039c984975c"
    ]

    # Sample item information
    item_caption = """🛍️ **Nike Sweater Grey**

🏷️ **Бренд:** Nike
📏 **Размер:** L
💰 **Цена:** 25.00 EUR (≈ 2,750.00 RUB)
📍 **Местоположение:** Vienna, Austria
⏰ **Загружено:** 08.09.2024
🔍 **Найдено по запросу:** Nike sweater

🔗 [Открыть на Vinted](https://www.vinted.at/items/7031727463-nike-sweater-grau-gr-146)"""

    print("🎯 DEMONSTRATION: Image URL Embedding (NO DOWNLOADS)")
    print("=" * 60)

    print("\n1️⃣  EXTRACTED IMAGE URLs:")
    for i, url in enumerate(sample_image_urls, 1):
        print(f"   {i}. {url}")

    print("\n2️⃣  CREATING TELEGRAM MEDIA GROUP:")
    print("   Using create_telegram_media_group() function...")

    # This is exactly what the bot does
    media_group, strategy = create_telegram_media_group(sample_image_urls, item_caption)

    print(f"   ✅ Created media group with {len(media_group)} items")
    print(f"   📋 Strategy used: {strategy}")

    print("\n3️⃣  MEDIA GROUP STRUCTURE:")
    for i, media_item in enumerate(media_group, 1):
        print(f"   Item {i}:")
        print(f"     - Media URL: {media_item.media}")
        if hasattr(media_item, 'caption') and media_item.caption:
            print(f"     - Has caption: ✅ ({len(media_item.caption)} chars)")
        else:
            print(f"     - Has caption: ❌")

    print("\n4️⃣  HOW BOT SENDS THIS:")
    print("   # Single image:")
    print("   await message.answer_photo(")
    print("       photo=media_group[0].media,")
    print("       caption=media_group[0].caption,")
    print("       parse_mode='Markdown'")
    print("   )")

    print("\n   # Multiple images:")
    print("   await message.answer_media_group(media_group)")

    print("\n5️⃣  RESULT IN TELEGRAM:")
    print("   📱 User sees: Image(s) embedded directly from URLs")
    print("   🔗 No downloads = Fast delivery")
    print("   💾 No local storage needed")
    print("   ⚡ Direct from Vinted CDN")

    print("\n" + "=" * 60)
    print("✅ SUCCESS: Images embedded without any downloads!")
    print("🚀 This is exactly what your bot does for every search result.")

if __name__ == "__main__":
    asyncio.run(demo_image_embedding())
