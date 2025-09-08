import asyncio
import time
from typing import Optional, Dict, Any
from datetime import datetime
from functools import partial

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from src.bot.handlers.search.search_states import SearchStates as PackageSearchStates

from src.bot.keyboards.search_keyboards import SearchKeyboards
from src.bot.keyboards import ReplyKeyboards
from src.bot.services.user_service import UserService
from src.bot.services.vinted_service import VintedService
from src.monitoring import get_logger
from src.error_handlers import ErrorHandler
from src.exceptions import VintedBotError


logger = get_logger(__name__)
router = Router()
user_service = UserService()

# Keep local alias to use in this module while exposing the package-level class
SearchStates = PackageSearchStates

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
            data = await state.get_data()
            was_searching = data.get('search_in_progress', False)

            # Clear any active search state
            await state.clear()
            logger.info(f"Search stopped for user {user_id}")

            if was_searching:
                await message.answer("🛑 Поиск остановлен пользователем.")
            else:
                await message.answer("Поиск остановлен. Возвращаемся к началу.")
        except Exception as e:
            logger.error(f"Error stopping search for user {user_id}: {e}")
            await message.answer("❌ Ошибка при остановке поиска.")

        welcome_text = "🛍️ Поиск на Vinted Austria\n\n🔍 Введите товары для поиска:\n• Nike, Adidas, Stone Island\n• \"Tommy Hilfiger\" для точного поиска\n\n🎯 Получите: свежие объявления с ценами и фото\n\nВведите товары:"
        await message.answer(welcome_text)

    async def _handle_search_flow(self, message: types.Message, state: FSMContext, user_id: int, text: str) -> None:
        """Handle search flow logic."""
        data = await state.get_data()

        # Check if there's an ongoing search
        if data.get('search_in_progress'):
            await message.answer(
                "🔄 Поиск уже выполняется. Пожалуйста, подождите завершения или используйте команду 'stop' для отмены."
            )
            return

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

            # Set search in progress state
            await state.update_data(search_in_progress=True, task_id=task_id)

            # Send immediate feedback that search started
            status_message = await message.answer(
                f"🔍 Поиск начат для: {', '.join(search_items)}\n"
                f"⏳ Результаты будут отправлены, как только поиск завершится.\n\n"
                f"💡 Вы можете продолжать пользоваться ботом во время поиска."
            )

            # Store the status message for potential updates
            await state.update_data(status_message_id=status_message.message_id)

            # Start search as background task with timeout
            search_task = asyncio.create_task(
                self._execute_search_with_timeout(user_id, search_items, max_results, message, state, task_id)
            )

            # Don't clear state immediately - let the search task handle it
            # This prevents confusion if search fails

        except Exception as e:
            logger.error(f"Error starting search for user {user_id}: {e}")
            await state.clear()  # Clear state on error
            await message.answer(
                "❌ Произошла ошибка при запуске поиска. Попробуйте позже."
            )

    async def _execute_search_with_timeout(self, user_id: int, search_items: list, max_results: int, message: types.Message, state: FSMContext, task_id: str) -> None:
        """Execute search with timeout protection."""
        try:
            # Set timeout for entire search operation (5 minutes max)
            search_timeout = 300  # 5 minutes

            # Create search coroutine
            search_coro = self._execute_search(user_id, search_items, max_results, message, state, task_id)

            # Execute with timeout
            await asyncio.wait_for(search_coro, timeout=search_timeout)

        except asyncio.TimeoutError:
            logger.error(f"Search timeout for user {user_id} after {search_timeout} seconds")
            await message.answer(
                "⏰ Поиск занимает слишком много времени. Попробуйте позже или уменьшите количество товаров для поиска."
            )
        except Exception as e:
            logger.error(f"Error in search timeout wrapper for user {user_id}: {e}")
            await message.answer("❌ Произошла ошибка при поиске. Попробуйте позже.")
        finally:
            # Always clear the search state when done
            try:
                current_data = await state.get_data()
                if current_data.get('task_id') == task_id:
                    await state.clear()
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up search state for user {user_id}: {cleanup_error}")

    async def _execute_search(self, user_id: int, search_items: list, max_results: int, message: types.Message, state: FSMContext, task_id: str) -> None:
        """Execute the actual search."""
        try:
            logger.info(f"Starting search for user {user_id}: {search_items}")

            # Use the vinted scraper - prioritize real data over mock
            from src.bot.services.vinted_scraper.scraper import SimpleVintedScraper
            from requests.exceptions import RequestException, Timeout, ConnectionError

            all_results = []
            search_errors = []

            # Try with SSL verification first, fallback to disabled if needed
            scraper = None
            ssl_disabled = False

            # Check environment settings for SSL verification
            from src.config import settings
            
            # Disable SSL in production or if explicitly configured
            use_ssl = not (settings.disable_ssl_verification or settings.is_production)
            
            try:
                scraper = SimpleVintedScraper(base_url="https://www.vinted.at", verify_ssl=use_ssl)
                ssl_status = "with SSL verification" if use_ssl else "without SSL verification"
                logger.info(f"Created scraper {ssl_status} (environment: {settings.environment})")
            except Exception as fallback_error:
                logger.error(f"Failed to create scraper: {fallback_error}")
                await message.answer(
                    "❌ Не удалось подключиться к сервису поиска. Попробуйте позже."
                )
                return

            try:
                with scraper:
                    total_terms = len(search_items)
                    for i, search_term in enumerate(search_items, 1):
                        try:
                            # Send progress update for multi-term searches
                            if total_terms > 1:
                                progress_msg = await message.answer(
                                    f"🔍 Поиск: {i}/{total_terms} - '{search_term}'..."
                                )

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

                                # Update progress with success
                                if total_terms > 1:
                                    try:
                                        await progress_msg.edit_text(
                                            f"✅ Найдено {len(items)} товаров для '{search_term}'"
                                        )
                                    except:
                                        pass  # Message might be too old to edit
                            else:
                                logger.warning(f"No items found for '{search_term}'")
                                # Update progress with no results
                                if total_terms > 1:
                                    try:
                                        await progress_msg.edit_text(
                                            f"❌ Ничего не найдено для '{search_term}'"
                                        )
                                    except:
                                        pass

                        except Timeout:
                            logger.error(f"Timeout searching for '{search_term}'")
                            search_errors.append(f"⏰ Таймаут для '{search_term}'")
                            if total_terms > 1:
                                try:
                                    await progress_msg.edit_text(
                                        f"⏰ Таймаут для '{search_term}'"
                                    )
                                except:
                                    pass
                            continue
                        except ConnectionError:
                            logger.error(f"Connection error searching for '{search_term}'")
                            search_errors.append(f"🌐 Ошибка соединения для '{search_term}'")
                            if total_terms > 1:
                                try:
                                    await progress_msg.edit_text(
                                        f"🌐 Ошибка соединения для '{search_term}'"
                                    )
                                except:
                                    pass
                            continue
                        except RequestException as e:
                            logger.error(f"Request error searching for '{search_term}': {e}")
                            search_errors.append(f"📡 Ошибка запроса для '{search_term}'")
                            if total_terms > 1:
                                try:
                                    await progress_msg.edit_text(
                                        f"📡 Ошибка запроса для '{search_term}'"
                                    )
                                except:
                                    pass
                            continue
                        except Exception as e:
                            # Check if it's an SSL error and try to retry without SSL verification
                            if "ssl" in str(e).lower() and not ssl_disabled:
                                logger.warning(f"SSL error for '{search_term}', retrying without SSL: {e}")
                                try:
                                    # Try this specific search without SSL
                                    with SimpleVintedScraper(base_url="https://www.vinted.at", verify_ssl=False) as ssl_scraper:
                                        items = ssl_scraper.search(
                                            search_text=search_term,
                                            page=1,
                                            per_page=min(max_results, 24)
                                        )
                                        if items:
                                            logger.info(f"Found {len(items)} items for '{search_term}' (retry without SSL)")
                                            for item in items:
                                                item['_search_term'] = search_term
                                            all_results.extend(items[:max_results])
                                            if total_terms > 1:
                                                try:
                                                    await progress_msg.edit_text(
                                                        f"✅ Найдено {len(items)} товаров для '{search_term}' (без SSL)"
                                                    )
                                                except:
                                                    pass
                                        continue
                                except Exception as retry_error:
                                    logger.error(f"Retry without SSL also failed for '{search_term}': {retry_error}")

                            logger.error(f"Unexpected error searching for '{search_term}': {e}")
                            search_errors.append(f"❌ Неизвестная ошибка для '{search_term}'")
                            if total_terms > 1:
                                try:
                                    await progress_msg.edit_text(
                                        f"❌ Ошибка для '{search_term}'"
                                    )
                                except:
                                    pass
                            continue
            except Exception as scraper_error:
                logger.error(f"Failed to initialize scraper: {scraper_error}")
                await message.answer(
                    "❌ Не удалось подключиться к сервису поиска. Попробуйте позже."
                )
                return

            # Limit total results
            all_results = all_results[:max_results]

            # Process images using our image service
            from src.bot.services.image import process_vinted_images
            processed_results = process_vinted_images(all_results)

            # Send results or error feedback
            if processed_results:
                await message.answer(f"✅ Найдено {len(processed_results)} товаров!")

                # Send each item with proper image handling
                for i, item in enumerate(processed_results, 1):
                    try:
                        formatted_item = await self._format_vinted_item(item, item.get('_search_term'))
                        
                        # Use our image service to send items with images
                        image_sent = await self._send_item_with_images(
                            message, item, formatted_item, i
                        )
                        
                        # Fallback to text-only if image delivery failed
                        if not image_sent:
                            # Re-format the item since formatted_item is already used
                            fallback_text = await self._format_vinted_item(item, item.get('_search_term'))
                            await message.answer(f"**Товар {i}**\n\n{fallback_text}", parse_mode='Markdown')

                        await asyncio.sleep(0.5)  # Small delay between items
                    except Exception as e:
                        logger.error(f"Error sending item {i}: {e}")
                        continue

                await message.answer("🎯 Поиск завершен!")

                # Report any partial errors
                if search_errors:
                    error_summary = "\n".join(search_errors[:3])  # Limit to first 3 errors
                    if len(search_errors) > 3:
                        error_summary += f"\n... и еще {len(search_errors) - 3} ошибок"
                    await message.answer(f"⚠️ Некоторые запросы завершились с ошибками:\n{error_summary}")

            else:
                if search_errors:
                    # All searches failed
                    error_summary = "\n".join(search_errors[:3])
                    if len(search_errors) > 3:
                        error_summary += f"\n... и еще {len(search_errors) - 3} ошибок"
                    await message.answer(
                        f"❌ Все поисковые запросы завершились с ошибками:\n{error_summary}\n\n"
                        f"Попробуйте позже или измените поисковые термины."
                    )
                else:
                    await message.answer("❌ По вашему запросу ничего не найдено. Попробуйте изменить поисковые термины.")

        except Exception as e:
            logger.error(f"Critical error executing search for user {user_id}: {e}")
            try:
                await message.answer(
                    "❌ Произошла критическая ошибка при поиске. Попробуйте позже."
                )
            except Exception as send_error:
                logger.error(f"Failed to send error message to user {user_id}: {send_error}")

    async def _format_vinted_item(self, item: dict, search_term: str = None) -> str:
        """Format Vinted item data for display."""
        try:
            # Debug: log the item structure
            logger.info(f"Formatting item: {list(item.keys())}")

            # Debug: log photo data
            photo_data = item.get('photo', {})
            logger.info(f"Photo data: {photo_data}")

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

            # Convert price to RUB if it's EUR
            price_display = ""
            if currency == 'EUR' and price > 0:
                from src.bot.services.currency_service import format_price_with_rub
                price_display = await format_price_with_rub(price)
            else:
                price_display = f"{price:.2f} {currency}"
            
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

            # Create formatted message
            message_parts = [f"🛍️ {title}"]
            if brand:
                message_parts.append(f"🏷️ Бренд: {brand}")
            if size:
                message_parts.append(f"📏 Размер: {size}")
            # Use the formatted price (with RUB conversion if applicable)
            message_parts.append(f"💰 Цена: {price_display}")
            message_parts.append(f"📍 Местоположение: {location if location else 'Не указано'}")
            if upload_time:
                message_parts.append(f"⏰ Загружено: {upload_time}")
            if search_term:
                message_parts.append(f"🔍 Найдено по запросу: {search_term}")
            if url:
                message_parts.append(f"🔗 [Открыть на Vinted]({url})")

            return '\n'.join(message_parts)

        except Exception as e:
            logger.error(f"Error formatting item: {e}")
            return f"🛍️ Товар\n❌ Ошибка при форматировании данных"

    async def _send_item_with_images(self, message: types.Message, item: dict, formatted_text: str, item_number: int) -> bool:
        """Send item with images using our LocalImageProcessor service."""
        try:
            from src.bot.services.image import get_image_processor, create_telegram_media_group

            # Get the image processor
            image_processor = get_image_processor()
            
            # Extract images from the item using the processor
            image_urls = image_processor.extract_images_from_item(item)
            if not image_urls:
                logger.debug(f"Item {item_number} has no images")
                return False

            logger.info(f"Item {item_number} has {len(image_urls)} image URLs")

            # Filter valid images
            valid_images = image_processor.filter_valid_images(image_urls)
            if not valid_images:
                logger.warning(f"No valid images found for item {item_number}")
                return False

            logger.info(f"Found {len(valid_images)} valid images for item {item_number}")

            # Create caption for the item
            caption = f"**Товар {item_number}**\n\n{formatted_text}"

            # Use the image service to create media group
            media_group, strategy = create_telegram_media_group(valid_images, caption)
            
            if not media_group:
                logger.warning(f"Failed to create media group for item {item_number} (strategy: {strategy})")
                return False

            logger.info(f"Created media group with {len(media_group)} items using strategy: {strategy}")

            # Send the media group
            if len(media_group) == 1:
                # Send single photo
                try:
                    await message.answer_photo(
                        photo=media_group[0].media,
                        caption=media_group[0].caption,
                        parse_mode='Markdown'
                    )
                    logger.info(f"Sent single image for item {item_number}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to send single image: {e}")
                    return False
            else:
                # Send media group
                try:
                    await message.answer_media_group(media_group)
                    logger.info(f"Sent media group ({len(media_group)} images) for item {item_number}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to send media group: {e}")
                    return False

        except Exception as e:
            logger.error(f"Error in _send_item_with_images for item {item_number}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False


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


__all__ = ["router"]