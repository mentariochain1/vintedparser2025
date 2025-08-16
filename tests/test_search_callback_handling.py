"""Tests for search callback query handling functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import types
from aiogram.fsm.context import FSMContext

from bot.handlers.search import (
    handle_item_count_selection,
    show_item_detail,
    show_item_photos,
    _handle_callback_fallback,
    _validate_callback_data,
    SearchStates
)
from bot.services.search_debugger import SearchErrorType, SearchStage


def create_mock_callback_query(data: str, user_id: int = 12345) -> types.CallbackQuery:
    """Create a mock callback query for testing."""
    callback = MagicMock(spec=types.CallbackQuery)
    callback.data = data
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.message.edit_media = AsyncMock()
    callback.message.answer = AsyncMock()
    return callback


class TestCallbackDataValidation:
    """Test callback data validation functions."""

    @pytest.mark.asyncio
    async def test_validate_callback_data_valid(self):
        """Test validation of valid callback data."""
        is_valid, payload = await _validate_callback_data("item_count:5", "item_count:")
        assert is_valid is True
        assert payload == "5"

    @pytest.mark.asyncio
    async def test_validate_callback_data_invalid_prefix(self):
        """Test validation with invalid prefix."""
        is_valid, error = await _validate_callback_data("wrong:5", "item_count:")
        assert is_valid is False
        assert "Invalid callback prefix" in error

    @pytest.mark.asyncio
    async def test_validate_callback_data_missing_separator(self):
        """Test validation with missing separator."""
        # Test case that has correct prefix but no separator
        is_valid, error = await _validate_callback_data("item_count:", "item_count:")
        assert is_valid is False
        assert "Empty callback payload" in error

    @pytest.mark.asyncio
    async def test_validate_callback_data_empty_payload(self):
        """Test validation with empty payload."""
        is_valid, error = await _validate_callback_data("item_count:", "item_count:")
        assert is_valid is False
        assert "Empty callback payload" in error

    @pytest.mark.asyncio
    async def test_validate_callback_data_none_input(self):
        """Test validation with None input."""
        is_valid, error = await _validate_callback_data(None, "item_count:")
        assert is_valid is False
        assert "Invalid callback prefix" in error


class TestCallbackFallback:
    """Test callback fallback handling."""

    @pytest.fixture
    def mock_callback(self):
        """Mock callback query."""
        callback = AsyncMock(spec=types.CallbackQuery)
        callback.answer = AsyncMock()
        callback.message = AsyncMock()
        callback.message.edit_text = AsyncMock()
        callback.message.answer = AsyncMock()
        return callback

    @pytest.fixture
    def mock_state(self):
        """Mock FSM state."""
        return AsyncMock(spec=FSMContext)

    @pytest.mark.asyncio
    async def test_callback_fallback_basic(self, mock_callback, mock_state):
        """Test basic callback fallback handling."""
        with patch('bot.handlers.search.SearchKeyboards') as mock_keyboards:
            mock_keyboards.create_error_keyboard.return_value = MagicMock()
            
            await _handle_callback_fallback(
                mock_callback, 
                "Test error message", 
                mock_state
            )
            
            mock_callback.answer.assert_called_once_with("Test error message", show_alert=True)
            mock_callback.message.edit_text.assert_called_once()
            mock_state.clear.assert_not_called()

    @pytest.mark.asyncio
    async def test_callback_fallback_with_state_clear(self, mock_callback, mock_state):
        """Test callback fallback with state clearing."""
        with patch('bot.handlers.search.SearchKeyboards') as mock_keyboards:
            mock_keyboards.create_error_keyboard.return_value = MagicMock()
            
            await _handle_callback_fallback(
                mock_callback, 
                "Test error message", 
                mock_state,
                clear_state=True
            )
            
            mock_callback.answer.assert_called_once_with("Test error message", show_alert=True)
            mock_state.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_callback_fallback_edit_fails(self, mock_callback, mock_state):
        """Test callback fallback when edit_text fails."""
        mock_callback.message.edit_text.side_effect = Exception("Edit failed")
        
        with patch('bot.handlers.search.SearchKeyboards') as mock_keyboards:
            mock_keyboards.create_error_keyboard.return_value = MagicMock()
            
            await _handle_callback_fallback(
                mock_callback, 
                "Test error message", 
                mock_state
            )
            
            mock_callback.answer.assert_called_once()
            mock_callback.message.answer.assert_called_once()


class TestItemCountCallback:
    """Test item count selection callback handling."""

    @pytest.fixture
    def mock_state(self):
        """Mock FSM state."""
        state = AsyncMock(spec=FSMContext)
        state.get_data.return_value = {
            'correlation_id': 'test123',
            'query': 'test query'
        }
        return state

    @pytest.fixture
    def mock_callback(self):
        """Mock callback query."""
        return create_mock_callback_query("item_count:5")

    @pytest.fixture
    def mock_search_debugger(self):
        """Mock search debugger."""
        with patch('bot.handlers.search.search_debugger') as mock:
            mock.create_correlation_id.return_value = 'test123'
            yield mock

    @pytest.fixture
    def mock_search_metrics(self):
        """Mock search metrics."""
        with patch('bot.handlers.search.search_metrics') as mock:
            yield mock

    @pytest.fixture
    def mock_handle_search(self):
        """Mock handle_search_query_with_count."""
        with patch('bot.handlers.search.handle_search_query_with_count') as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_item_count_callback_success(
        self, 
        mock_callback, 
        mock_state, 
        mock_search_debugger,
        mock_search_metrics,
        mock_handle_search
    ):
        """Test successful item count callback handling."""
        await handle_item_count_selection(mock_callback, mock_state)
        
        mock_callback.answer.assert_called_with("✅ Выбрано: 5 товаров")
        mock_state.update_data.assert_called_with(item_count=5)
        mock_handle_search.assert_called_once()
        mock_search_metrics.record_callback_operation.assert_called()

    @pytest.mark.asyncio
    async def test_item_count_callback_custom(
        self, 
        mock_state, 
        mock_search_debugger,
        mock_search_metrics
    ):
        """Test custom item count selection."""
        callback = create_mock_callback_query("item_count:custom")
        
        await handle_item_count_selection(callback, mock_state)
        
        callback.message.edit_text.assert_called_once()
        mock_state.set_state.assert_called_with(SearchStates.waiting_for_item_count)
        callback.answer.assert_called_with("✏️ Введи своё количество")

    @pytest.mark.asyncio
    async def test_item_count_callback_invalid_format(
        self, 
        mock_state, 
        mock_search_debugger,
        mock_search_metrics
    ):
        """Test invalid callback data format."""
        callback = create_mock_callback_query("item_count")  # Missing separator
        
        with patch('bot.handlers.search._handle_callback_fallback') as mock_fallback:
            await handle_item_count_selection(callback, mock_state)
            mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_item_count_callback_invalid_number(
        self, 
        mock_state, 
        mock_search_debugger,
        mock_search_metrics
    ):
        """Test invalid item count number."""
        callback = create_mock_callback_query("item_count:abc")  # Invalid number
        
        with patch('bot.handlers.search._handle_callback_fallback') as mock_fallback:
            await handle_item_count_selection(callback, mock_state)
            mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_item_count_callback_out_of_range(
        self, 
        mock_state, 
        mock_search_debugger,
        mock_search_metrics
    ):
        """Test item count out of valid range."""
        callback = create_mock_callback_query("item_count:150")  # Too high
        
        with patch('bot.handlers.search._handle_callback_fallback') as mock_fallback:
            await handle_item_count_selection(callback, mock_state)
            mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_item_count_callback_missing_query(
        self, 
        mock_search_debugger,
        mock_search_metrics
    ):
        """Test callback when query is missing from state."""
        state = AsyncMock(spec=FSMContext)
        state.get_data.return_value = {
            'correlation_id': 'test123'
            # Missing 'query'
        }
        
        callback = create_mock_callback_query("item_count:5")
        
        with patch('bot.handlers.search._handle_callback_fallback') as mock_fallback:
            await handle_item_count_selection(callback, state)
            mock_fallback.assert_called_once()
            # Check that clear_state=True was passed
            args, kwargs = mock_fallback.call_args
            assert kwargs.get('clear_state') is True


class TestItemDetailCallback:
    """Test item detail callback handling."""

    @pytest.fixture
    def mock_callback(self):
        """Mock callback query."""
        return create_mock_callback_query("item_detail:123")

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        with patch('bot.handlers.search.get_db_session') as mock:
            session = AsyncMock()
            # Create a proper async context manager
            async_context = AsyncMock()
            async_context.__aenter__ = AsyncMock(return_value=session)
            async_context.__aexit__ = AsyncMock(return_value=None)
            mock.return_value = async_context
            yield session

    @pytest.fixture
    def mock_item_crud(self):
        """Mock ItemCRUD."""
        with patch('bot.handlers.search.ItemCRUD') as mock:
            # Make the methods async
            mock.get_by_id = AsyncMock()
            yield mock

    @pytest.fixture
    def mock_photo_crud(self):
        """Mock PhotoCRUD."""
        with patch('bot.handlers.search.PhotoCRUD') as mock:
            # Make the methods async
            mock.get_by_item_id = AsyncMock()
            yield mock

    @pytest.fixture
    def mock_search_debugger(self):
        """Mock search debugger."""
        with patch('bot.handlers.search.search_debugger') as mock:
            mock.create_correlation_id.return_value = 'test123'
            yield mock

    @pytest.mark.asyncio
    async def test_item_detail_callback_success_with_photos(
        self, 
        mock_callback, 
        mock_db_session,
        mock_item_crud,
        mock_photo_crud,
        mock_search_debugger
    ):
        """Test successful item detail display with photos."""
        # Mock item
        mock_item = MagicMock()
        mock_item.id = 123
        mock_item.title = "Test Item"
        mock_item.price = 25.99
        mock_item.currency = "EUR"
        mock_item.brand = "Nike"
        mock_item.size = "M"
        mock_item.condition = "Good"
        mock_item.description = "Test description"
        mock_item.url = "https://vinted.at/items/123"
        mock_item_crud.get_by_id.return_value = mock_item

        # Mock photos
        mock_photo = MagicMock()
        mock_photo.url = "https://example.com/photo1.jpg"
        mock_photo.order_no = 0
        mock_photo_crud.get_by_item_id.return_value = [mock_photo]

        with patch('bot.handlers.search.format_item_detail') as mock_format:
            mock_format.return_value = "Formatted item text"
            with patch('bot.handlers.search.SearchKeyboards') as mock_keyboards:
                mock_keyboards.create_item_detail_keyboard.return_value = MagicMock()
                
                await show_item_detail(mock_callback)
                
                mock_item_crud.get_by_id.assert_called_once_with(mock_db_session, 123)
                mock_photo_crud.get_by_item_id.assert_called_once_with(mock_db_session, 123)
                mock_callback.message.edit_media.assert_called_once()
                mock_callback.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_item_detail_callback_item_not_found(
        self, 
        mock_callback, 
        mock_db_session,
        mock_item_crud,
        mock_photo_crud,
        mock_search_debugger
    ):
        """Test item detail when item not found."""
        mock_item_crud.get_by_id.return_value = None
        
        await show_item_detail(mock_callback)
        
        mock_callback.answer.assert_called_once_with("❌ Товар не найден", show_alert=True)

    @pytest.mark.asyncio
    async def test_item_detail_callback_invalid_id(
        self, 
        mock_search_debugger
    ):
        """Test item detail with invalid item ID."""
        callback = create_mock_callback_query("item_detail:abc")  # Invalid ID
        
        await show_item_detail(callback)
        
        callback.answer.assert_called_once_with("❌ Неверный ID товара", show_alert=True)

    @pytest.mark.asyncio
    async def test_item_detail_callback_display_fallback(
        self, 
        mock_callback, 
        mock_db_session,
        mock_item_crud,
        mock_photo_crud,
        mock_search_debugger
    ):
        """Test item detail display fallback when media fails."""
        # Mock item
        mock_item = MagicMock()
        mock_item.id = 123
        mock_item.title = "Test Item"
        mock_item.price = 25.99
        mock_item.currency = "EUR"
        mock_item.brand = "Nike"
        mock_item.size = "M"
        mock_item.condition = "Good"
        mock_item.description = "Test description"
        mock_item.url = "https://vinted.at/items/123"
        mock_item_crud.get_by_id.return_value = mock_item

        # Mock photos
        mock_photo = MagicMock()
        mock_photo.url = "https://example.com/photo1.jpg"
        mock_photo.order_no = 0
        mock_photo_crud.get_by_item_id.return_value = [mock_photo]

        # Make edit_media fail
        mock_callback.message.edit_media.side_effect = Exception("Media failed")

        with patch('bot.handlers.search.format_item_detail') as mock_format:
            mock_format.return_value = "Formatted item text"
            with patch('bot.handlers.search.SearchKeyboards') as mock_keyboards:
                mock_keyboards.create_item_detail_keyboard.return_value = MagicMock()
                
                await show_item_detail(mock_callback)
                
                # Should fallback to text display
                mock_callback.message.edit_text.assert_called_once()
                mock_callback.answer.assert_called_once()


class TestItemPhotosCallback:
    """Test item photos callback handling."""

    @pytest.fixture
    def mock_callback(self):
        """Mock callback query."""
        return create_mock_callback_query("item_photos:123:0")

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        with patch('bot.handlers.search.get_db_session') as mock:
            session = AsyncMock()
            # Create a proper async context manager
            async_context = AsyncMock()
            async_context.__aenter__ = AsyncMock(return_value=session)
            async_context.__aexit__ = AsyncMock(return_value=None)
            mock.return_value = async_context
            yield session

    @pytest.fixture
    def mock_item_crud(self):
        """Mock ItemCRUD."""
        with patch('bot.handlers.search.ItemCRUD') as mock:
            # Make the methods async
            mock.get_by_id = AsyncMock()
            yield mock

    @pytest.fixture
    def mock_photo_crud(self):
        """Mock PhotoCRUD."""
        with patch('bot.handlers.search.PhotoCRUD') as mock:
            # Make the methods async
            mock.get_by_item_id = AsyncMock()
            yield mock

    @pytest.fixture
    def mock_search_debugger(self):
        """Mock search debugger."""
        with patch('bot.handlers.search.search_debugger') as mock:
            mock.create_correlation_id.return_value = 'test123'
            yield mock

    @pytest.mark.asyncio
    async def test_item_photos_callback_success(
        self, 
        mock_callback, 
        mock_db_session,
        mock_item_crud,
        mock_photo_crud,
        mock_search_debugger
    ):
        """Test successful photo navigation."""
        # Mock item
        mock_item = MagicMock()
        mock_item.id = 123
        mock_item.title = "Test Item"
        mock_item.price = 25.99
        mock_item.currency = "EUR"
        mock_item.brand = "Nike"
        mock_item_crud.get_by_id.return_value = mock_item

        # Mock photos
        mock_photos = []
        for i in range(3):
            photo = MagicMock()
            photo.url = f"https://example.com/photo{i}.jpg"
            photo.order_no = i
            mock_photos.append(photo)
        mock_photo_crud.get_by_item_id.return_value = mock_photos

        with patch('bot.handlers.search.SearchKeyboards') as mock_keyboards:
            mock_keyboards.create_photo_navigation_keyboard.return_value = MagicMock()
            
            await show_item_photos(mock_callback)
            
            mock_item_crud.get_by_id.assert_called_once_with(mock_db_session, 123)
            mock_photo_crud.get_by_item_id.assert_called_once_with(mock_db_session, 123)
            mock_callback.message.edit_media.assert_called_once()
            mock_callback.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_item_photos_callback_invalid_format(
        self, 
        mock_search_debugger
    ):
        """Test photo callback with invalid format."""
        callback = create_mock_callback_query("item_photos:123")  # Missing photo index
        
        await show_item_photos(callback)
        
        callback.answer.assert_called_once_with("❌ Неверный формат данных фото", show_alert=True)

    @pytest.mark.asyncio
    async def test_item_photos_callback_invalid_item_id(
        self, 
        mock_search_debugger
    ):
        """Test photo callback with invalid item ID."""
        callback = create_mock_callback_query("item_photos:abc:0")  # Invalid item ID
        
        await show_item_photos(callback)
        
        callback.answer.assert_called_once_with("❌ Неверные параметры фото", show_alert=True)

    @pytest.mark.asyncio
    async def test_item_photos_callback_no_photos(
        self, 
        mock_callback, 
        mock_db_session,
        mock_item_crud,
        mock_photo_crud,
        mock_search_debugger
    ):
        """Test photo callback when no photos exist."""
        mock_item = MagicMock()
        mock_item_crud.get_by_id.return_value = mock_item
        mock_photo_crud.get_by_item_id.return_value = []  # No photos
        
        await show_item_photos(mock_callback)
        
        mock_callback.answer.assert_called_once_with("❌ Фото не найдены", show_alert=True)

    @pytest.mark.asyncio
    async def test_item_photos_callback_display_fallback(
        self, 
        mock_callback, 
        mock_db_session,
        mock_item_crud,
        mock_photo_crud,
        mock_search_debugger
    ):
        """Test photo display fallback when media fails."""
        # Mock item
        mock_item = MagicMock()
        mock_item.id = 123
        mock_item.title = "Test Item"
        mock_item.price = 25.99
        mock_item.currency = "EUR"
        mock_item.brand = "Nike"
        mock_item_crud.get_by_id.return_value = mock_item

        # Mock photos
        mock_photo = MagicMock()
        mock_photo.url = "https://example.com/photo1.jpg"
        mock_photo.order_no = 0
        mock_photo_crud.get_by_item_id.return_value = [mock_photo]

        # Make edit_media fail
        mock_callback.message.edit_media.side_effect = Exception("Media failed")

        with patch('bot.handlers.search.SearchKeyboards') as mock_keyboards:
            mock_keyboards.create_photo_navigation_keyboard.return_value = MagicMock()
            
            await show_item_photos(mock_callback)
            
            # Should fallback to text display
            mock_callback.message.edit_text.assert_called_once()
            mock_callback.answer.assert_called_with("❌ Изображение недоступно")


class TestCallbackErrorScenarios:
    """Test various error scenarios in callback handling."""

    @pytest.mark.asyncio
    async def test_callback_with_none_data(self):
        """Test callback handling with None data."""
        callback = create_mock_callback_query(None)
        
        state = AsyncMock(spec=FSMContext)
        state.get_data.return_value = {'correlation_id': 'test123'}
        
        with patch('bot.handlers.search.search_debugger') as mock_debugger:
            mock_debugger.create_correlation_id.return_value = 'test123'
            with patch('bot.handlers.search._handle_callback_fallback') as mock_fallback:
                await handle_item_count_selection(callback, state)
                mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_callback_with_empty_data(self):
        """Test callback handling with empty data."""
        callback = create_mock_callback_query("")
        
        state = AsyncMock(spec=FSMContext)
        state.get_data.return_value = {'correlation_id': 'test123'}
        
        with patch('bot.handlers.search.search_debugger') as mock_debugger:
            mock_debugger.create_correlation_id.return_value = 'test123'
            with patch('bot.handlers.search._handle_callback_fallback') as mock_fallback:
                await handle_item_count_selection(callback, state)
                mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_callback_state_get_data_fails(self):
        """Test callback when state.get_data() fails."""
        callback = create_mock_callback_query("item_count:5")
        
        state = AsyncMock(spec=FSMContext)
        state.get_data.side_effect = Exception("State error")
        
        with patch('bot.handlers.search.search_debugger') as mock_debugger:
            mock_debugger.create_correlation_id.return_value = 'test123'
            with patch('bot.handlers.search.search_metrics') as mock_metrics:
                with patch('bot.handlers.search._handle_callback_fallback') as mock_fallback:
                    # The function should handle the exception and call fallback
                    await handle_item_count_selection(callback, state)
                    mock_fallback.assert_called_once()