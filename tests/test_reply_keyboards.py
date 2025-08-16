"""Tests for reply keyboard functionality."""

import pytest
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from bot.keyboards.reply_keyboards import ReplyKeyboards


class TestReplyKeyboards:
    """Test reply keyboard creation and functionality."""

    def test_main_menu_keyboard(self):
        """Test main menu keyboard creation."""
        keyboard = ReplyKeyboards.main_menu()
        
        assert isinstance(keyboard, ReplyKeyboardMarkup)
        assert keyboard.resize_keyboard is True
        assert keyboard.persistent is True
        assert "Choose an action" in keyboard.input_field_placeholder
        
        # Check button structure
        assert len(keyboard.keyboard) == 2  # 2 rows
        assert len(keyboard.keyboard[0]) == 2  # First row has 2 buttons
        assert len(keyboard.keyboard[1]) == 2  # Second row has 2 buttons
        
        # Check button texts
        buttons_text = []
        for row in keyboard.keyboard:
            for button in row:
                buttons_text.append(button.text)
        
        expected_buttons = ["🔍 Поиск", "💎 Премиум", "👥 Реферал", "📊 Статус"]
        assert buttons_text == expected_buttons

    def test_search_menu_keyboard(self):
        """Test search menu keyboard creation."""
        keyboard = ReplyKeyboards.search_menu()
        
        assert isinstance(keyboard, ReplyKeyboardMarkup)
        assert keyboard.resize_keyboard is True
        assert keyboard.persistent is True
        assert "Type your search" in keyboard.input_field_placeholder
        
        # Check button structure
        assert len(keyboard.keyboard) == 2  # 2 rows
        assert keyboard.keyboard[0][0].text == "🔍 Новый поиск"
        assert keyboard.keyboard[1][0].text == "🏠 Главное меню"

    def test_premium_menu_keyboard(self):
        """Test premium menu keyboard creation."""
        keyboard = ReplyKeyboards.premium_menu()
        
        assert isinstance(keyboard, ReplyKeyboardMarkup)
        assert keyboard.resize_keyboard is True
        assert keyboard.persistent is True
        
        # Check button structure
        assert len(keyboard.keyboard) == 2  # 2 rows
        assert len(keyboard.keyboard[0]) == 2  # First row has 2 buttons
        assert len(keyboard.keyboard[1]) == 2  # Second row has 2 buttons

    def test_hide_keyboard(self):
        """Test keyboard hiding functionality."""
        from aiogram.types import ReplyKeyboardRemove
        
        result = ReplyKeyboards.hide_keyboard()
        assert isinstance(result, ReplyKeyboardRemove)