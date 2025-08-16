"""Reply keyboard utilities for persistent bot navigation."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

class ReplyKeyboards:
    """Utility class for creating reply keyboards (persistent buttons under input)."""

    @staticmethod
    def main_menu() -> ReplyKeyboardMarkup:
        """
        Create main menu reply keyboard with core functions.
        
        Returns:
            ReplyKeyboardMarkup with main navigation buttons
        """
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🔍 Поиск"), KeyboardButton(text="💎 Премиум")],
                [KeyboardButton(text="👥 Реферал"), KeyboardButton(text="📊 Статус")],
            ],
            resize_keyboard=True,
            persistent=True,
            input_field_placeholder="Выберите действие или введите запрос...",
        )
        return keyboard

    @staticmethod
    def search_menu() -> ReplyKeyboardMarkup:
        """
        Create search-focused reply keyboard.
        
        Returns:
            ReplyKeyboardMarkup with search options
        """
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🔍 Новый поиск")],
                [KeyboardButton(text="🏠 Главное меню")],
            ],
            resize_keyboard=True,
            persistent=True,
            input_field_placeholder="Введите поисковый запрос...",
        )
        return keyboard

    @staticmethod
    def premium_menu() -> ReplyKeyboardMarkup:
        """
        Create premium-focused reply keyboard.
        
        Returns:
            ReplyKeyboardMarkup with premium options
        """
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="💳 Подписка"), KeyboardButton(text="📊 Статус")],
                [KeyboardButton(text="👥 Реферальная ссылка"), KeyboardButton(text="🏠 Главное меню")],
            ],
            resize_keyboard=True,
            persistent=True,
            input_field_placeholder="Выберите опцию премиума...",
        )
        return keyboard

    @staticmethod
    def hide_keyboard() -> ReplyKeyboardMarkup:
        """
        Hide the reply keyboard.
        
        Returns:
            ReplyKeyboardRemove to hide persistent buttons
        """
        from aiogram.types import ReplyKeyboardRemove
        return ReplyKeyboardRemove()