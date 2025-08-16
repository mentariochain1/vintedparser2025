import asyncio
import time
from typing import Optional, Dict, Any
from datetime import datetime

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards.search_keyboards import SearchKeyboards
from bot.keyboards import ReplyKeyboards
from bot.services.user_service import UserService
from bot.services.vinted_service import VintedService
from monitoring import get_logger
from error_handlers import ErrorHandler
from exceptions import VintedBotError


logger = get_logger(__name__)
router = Router()
user_service = UserService()

class SearchStates(StatesGroup):
    waiting_for_query = State()
    waiting_for_item_count = State()

_search_cache: Dict[str, Dict[str, Any]] = {}

class MessageHandler:
    """Handles incoming text messages with concurrent processing support."""
    
    def __init__(self):
        self.error_handler = ErrorHandler()

    async def handle_text_message(self, message: types.Message, state: FSMContext) -> None:
        """Handle incoming text messages with concurrent processing support."""
        user_id = message.from_user.id
        text = message.text.strip() if message.text else ""
        logger.info(f"Received message from user {user_id}: {text}")

        # Check if user wants to stop the search
        if text.lower() == "stop":
            await self._handle_stop_command(message, state, user_id)
            return

        # Handle search flow with concurrent processing
        try:
            await self._handle_search_flow(message, state, user_id, text)
        except Exception as e:
            logger.error(f"Error handling text message from user {user_id}: {e}")
            await message.answer(
                "❌ Произошла ошибка при обработке сообщения. Попробуйте еще раз."
            )

    async def _handle_stop_command(self, message: types.Message, state: FSMContext, user_id: int) -> None:
        """Handle stop command from user."""
        try:
            # Clear any active search state
            await state.clear()
            logger.info(f"Search stopped for user {user_id}")
        except Exception as e:
            logger.error(f"Error stopping search for user {user_id}: {e}")
                
        await message.answer("Поиск остановлен. Возвращаемся к началу.")
        welcome_text = "🛍️ Поиск на Vinted Austria\n\n🔍 Введите товары для поиска:\n• Nike, Adidas, Stone Island\n• \"Tommy Hilfiger\" для точного поиска\n\n🎯 Получите: свежие объявления с ценами и фото\n\nВведите товары:"
        await message.answer(welcome_text)

    async def _handle_search_flow(self, message: types.Message, state: FSMContext, user_id: int, text: str) -> None:
        """Handle search flow logic."""
        data = await state.get_data()
        
        if not data.get('search_items'):
            await self._handle_search_items_input(message, state, text)
        elif not data.get('max_results'):
            await self._handle_max_results_input(message, state, text, user_id)
        else:
            await self._handle_existing_search(message, user_id)

    async def _handle_search_items_input(self, message: types.Message, state: FSMContext, text: str) -> None:
        """Handle search items input from user."""
        # Simple parsing - split by comma and clean up
        items = [item.strip().strip('"\'') for item in text.split(',') if item.strip()]
        if not items:
            # Try splitting by newlines
            items = [item.strip().strip('"\'') for item in text.split('\n') if item.strip()]
        
        if items:
            await state.update_data(search_items=items)
            items_preview = ', '.join(items)
            await message.answer(
                f"🔍 Будем искать: {items_preview}\n\n"
                f"Укажите максимальное количество результатов для отображения (число от 1 до 100).\n\n"
                f"Оставьте поле пустым для значения по умолчанию — 5 результатов.\n\n"
                f"💡 Совет: Используйте кавычки для точного поиска, например: \"Stone Island\""
            )
        else:
            await message.answer(
                "Пожалуйста, введите хотя бы один товар для поиска.\n\n"
                "💡 Примеры:\n"
                "• Nike, Adidas, Puma\n"
                "• \"Stone Island\" \"Ralph Lauren\"\n"
                "• Nike\n• Adidas\n• Stone Island"
            )

    async def _handle_max_results_input(self, message: types.Message, state: FSMContext, text: str, user_id: int) -> None:
        """Handle max results input from user."""
        try:
            max_results = int(text) if text else 5
            if 1 <= max_results <= 100:
                await state.update_data(max_results=max_results)
                                
                await message.answer(
                    f"🔍 Установлено количество результатов: {max_results}. Начинаем поиск..."
                )
                # Start search process
                await self.start_search(message, state)
            else:
                await message.answer(
                    "Пожалуйста, укажите число от 1 до 100."
                )
        except ValueError:
            await message.answer(
                "Пожалуйста, введите корректное число или оставьте поле пустым для значения по умолчанию (5)."
            )

    async def _handle_existing_search(self, message: types.Message, user_id: int) -> None:
        """Handle case when user already has search parameters set."""
        await message.answer(
            "Поиск завершен. Введите новые товары для поиска или используйте команду /search."
        )

    async def start_search(self, message: types.Message, state: FSMContext) -> None:
        """Start the search process."""
        user_id = message.from_user.id
        data = await state.get_data()
        search_items = data.get('search_items', [])
        max_results = data.get('max_results', 5)
                
        try:
            # Generate simple task ID
            task_id = f"search_{user_id}_{int(time.time())}"
                        
            # Send immediate feedback that search started
            await message.answer(
                f"🔍 Поиск начат для: {', '.join(search_items)}\n"
                f"⏳ Результаты будут отправлены, как только поиск завершится."
            )
                        
            # Start search as background task
            asyncio.create_task(self._execute_search(user_id, search_items, max_results, message, task_id))
            
            # Clear state after starting search
            await state.clear()
                    
        except Exception as e:
            logger.error(f"Error starting search for user {user_id}: {e}")
            await message.answer(
                "❌ Произошла ошибка при запуске поиска. Попробуйте позже."
            )

    async def _execute_search(self, user_id: int, search_items: list, max_results: int, message: types.Message, task_id: str) -> None:
        """Execute the actual search."""
        try:
            logger.info(f"Starting search for user {user_id}: {search_items}")
            
            # Use the vinted scraper directly with SSL disabled for better reliability
            from bot.services.vinted_scraper.scraper import SimpleVintedScraper
            
            all_results = []
            
            # Create scraper with SSL verification disabled to avoid certificate issues
            with SimpleVintedScraper(base_url="https://www.vinted.at", verify_ssl=False) as scraper:
                for search_term in search_items:
                    try:
                        logger.info(f"Searching Vinted for: {search_term}")
                        
                        # Search with the scraper
                        items = scraper.search(
                            search_text=search_term,
                            page=1,
                            per_page=min(max_results, 24)
                        )
                        
                        if items:
                            logger.info(f"Found {len(items)} items for '{search_term}'")
                            # Add search term to each item for context
                            for item in items:
                                item['_search_term'] = search_term
                            all_results.extend(items[:max_results])
                        else:
                            logger.warning(f"No items found for '{search_term}'")
                            
                    except Exception as e:
                        logger.error(f"Error searching for '{search_term}': {e}")
                        # Continue with other search terms even if one fails
                        continue
            
            # Limit total results
            all_results = all_results[:max_results]
            
            if all_results:
                await message.answer(f"✅ Найдено {len(all_results)} товаров!")
                
                # Send each item
                for i, item in enumerate(all_results, 1):
                    try:
                        formatted_item = self._format_vinted_item(item, item.get('_search_term'))
                        await message.answer(f"**Товар {i}**\n\n{formatted_item}", parse_mode='Markdown')
                        await asyncio.sleep(0.5)  # Small delay between items
                    except Exception as e:
                        logger.error(f"Error sending item {i}: {e}")
                        continue
                        
                await message.answer("🎯 Поиск завершен!")
            else:
                await message.answer("❌ По вашему запросу ничего не найдено. Попробуйте изменить поисковые термины.")
                
        except Exception as e:
            logger.error(f"Error executing search for user {user_id}: {e}")
            await message.answer("❌ Произошла ошибка при поиске. Попробуйте позже.")

    def _format_vinted_item(self, item: dict, search_term: str = None) -> str:
        """Format Vinted item data for display."""
        try:
            # Debug: log the item structure
            logger.info(f"Formatting item: {list(item.keys())}")
            
            # Extract data from vinted scraper structure
            title = item.get('title', 'Unknown Item')
            
            # Handle price structure from vinted scraper
            price_info = item.get('price', {})
            if isinstance(price_info, dict):
                price_raw = price_info.get('amount', 0.0)
                currency = price_info.get('currency_code', 'EUR')
                # Ensure price is a float
                try:
                    price = float(price_raw) if price_raw is not None else 0.0
                except (ValueError, TypeError):
                    price = 0.0
            else:
                price = 0.0
                currency = 'EUR'
            
            # Handle brand structure
            brand_info = item.get('brand', {})
            brand = brand_info.get('title', '') if isinstance(brand_info, dict) else ''
            
            # Handle size structure
            size_info = item.get('size', {})
            size = size_info.get('title', '') if isinstance(size_info, dict) else ''
            
            # Handle user/location structure
            user_info = item.get('user', {})
            location = user_info.get('city', '') if isinstance(user_info, dict) else ''
            
            # Get URL
            url = item.get('url', '')
            
            # Get upload time if available
            upload_time = item.get('created_at_ts', '')
            if upload_time:
                try:
                    from datetime import datetime
                    dt = datetime.fromtimestamp(upload_time)
                    upload_time = dt.strftime('%d.%m.%Y')
                except:
                    upload_time = ''

            # Check if this is mock data
            is_mock = item.get('_mock', False)
            is_realistic = item.get('_realistic', False)

            # Create formatted message
            message_parts = [f"🛍️ {title}"]
            if brand:
                message_parts.append(f"🏷️ Бренд: {brand}")
            if size:
                message_parts.append(f"📏 Размер: {size}")
            # Format price safely
            try:
                price_str = f"{price:.2f}" if isinstance(price, (int, float)) else str(price)
                message_parts.append(f"💰 Цена: {price_str} {currency}")
            except Exception as price_error:
                logger.error(f"Error formatting price {price}: {price_error}")
                message_parts.append(f"💰 Цена: {price} {currency}")
            message_parts.append(f"📍 Местоположение: {location if location else 'Не указано'}")
            if upload_time:
                message_parts.append(f"⏰ Загружено: {upload_time}")
            if search_term:
                message_parts.append(f"🔍 Найдено по запросу: {search_term}")
            if url:
                message_parts.append(f"🔗 [Открыть на Vinted]({url})")
            
            # Add debug info if mock data
            if is_mock and is_realistic:
                message_parts.append(f"\n⚠️ Демо-данные (Vinted API недоступен)")
                
            return '\n'.join(message_parts)
            
        except Exception as e:
            logger.error(f"Error formatting item: {e}")
            return f"🛍️ Товар\n❌ Ошибка при форматировании данных"


# Global message handler instance
_message_handler = None

def get_message_handler() -> MessageHandler:
    """Get the global message handler instance."""
    global _message_handler
    if _message_handler is None:
        _message_handler = MessageHandler()
    return _message_handler

@router.message(Command("search"))
async def search_command(message: types.Message, state: FSMContext) -> None:
    """Handle /search command."""
    await state.clear()
    await message.answer(
        "🔍 Готов к поиску.\n\n"
        "Просто напиши, что найти. Например: <code>кроссовки Nike</code> или <code>винтажная куртка</code>.",
        parse_mode='HTML'
    )
    await state.set_state(SearchStates.waiting_for_query)

@router.message(SearchStates.waiting_for_query)
async def process_search_query(message: types.Message, state: FSMContext) -> None:
    """Process search query input."""
    handler = get_message_handler()
    await handler.handle_text_message(message, state)

@router.message(SearchStates.waiting_for_item_count)
async def process_item_count(message: types.Message, state: FSMContext) -> None:
    """Process item count input."""
    handler = get_message_handler()
    await handler.handle_text_message(message, state)