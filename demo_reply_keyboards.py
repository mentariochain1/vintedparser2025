#!/usr/bin/env python3
"""
Demo script showing reply keyboard functionality.

This demonstrates the persistent buttons that appear under the text input.
"""

import sys
import os
sys.path.insert(0, 'src')

from bot.keyboards.reply_keyboards import ReplyKeyboards

def demo_reply_keyboards():
    """Demonstrate reply keyboard creation and structure."""
    
    print("🎯 Демо русских клавиатур")
    print("=" * 50)
    
    # Main menu keyboard
    print("\n1. Main Menu Keyboard:")
    main_kb = ReplyKeyboards.main_menu()
    print(f"   Persistent: {main_kb.persistent}")
    print(f"   Resize: {main_kb.resize_keyboard}")
    print(f"   Placeholder: {main_kb.input_field_placeholder}")
    print("   Buttons:")
    for i, row in enumerate(main_kb.keyboard):
        print(f"     Row {i+1}: {[btn.text for btn in row]}")
    
    # Search menu keyboard
    print("\n2. Search Menu Keyboard:")
    search_kb = ReplyKeyboards.search_menu()
    print(f"   Persistent: {search_kb.persistent}")
    print(f"   Placeholder: {search_kb.input_field_placeholder}")
    print("   Buttons:")
    for i, row in enumerate(search_kb.keyboard):
        print(f"     Row {i+1}: {[btn.text for btn in row]}")
    
    # Premium menu keyboard
    print("\n3. Premium Menu Keyboard:")
    premium_kb = ReplyKeyboards.premium_menu()
    print(f"   Persistent: {premium_kb.persistent}")
    print("   Buttons:")
    for i, row in enumerate(premium_kb.keyboard):
        print(f"     Row {i+1}: {[btn.text for btn in row]}")
    
    print("\n" + "=" * 50)
    print("✅ Все клавиатуры созданы успешно!")
    print("\nЭти клавиатуры будут отображаться как постоянные кнопки")
    print("под полем ввода текста в вашем Telegram боте.")
    print("\nОсновные функции:")
    print("• Persistent: Остаются видимыми между сообщениями")
    print("• Resize: Подстраиваются под размер контента")
    print("• Placeholder: Показывают подсказки в поле ввода")

if __name__ == "__main__":
    demo_reply_keyboards()