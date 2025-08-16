"""Integration tests for search callback query handling."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import types
from aiogram.fsm.context import FSMContext

from bot.handlers.search import handle_item_count_selection, SearchStates


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


class TestCallbackIntegration:
    """Integration tests for callback handling."""

    @pytest.mark.asyncio
    async def test_complete_item_count_callback_flow(self):
        """Test complete item count callback flow from start to search execution."""
        # Setup
        callback = create_mock_callback_query("item_count:10")
        
        state = AsyncMock(spec=FSMContext)
        state.get_data.return_value = {
            'correlation_id': 'test123',
            'query': 'Nike sneakers'
        }
        
        # Mock all dependencies
        with patch('bot.handlers.search.search_debugger') as mock_debugger, \
             patch('bot.handlers.search.search_metrics') as mock_metrics, \
             patch('bot.handlers.search.handle_search_query_with_count') as mock_search:
            
            mock_debugger.create_correlation_id.return_value = 'test123'
            
            # Execute
            await handle_item_count_selection(callback, state)
            
            # Verify callback was answered
            callback.answer.assert_called_once_with("✅ Выбрано: 10 товаров")
            
            # Verify state was updated
            state.update_data.assert_called_once_with(item_count=10)
            
            # Verify search was initiated
            mock_search.assert_called_once()
            args = mock_search.call_args[0]
            assert args[1] == 'Nike sneakers'  # query
            assert args[2] == 10  # item_count
            
            # Verify metrics were recorded
            mock_metrics.record_callback_operation.assert_called()
            
            # Verify debugging was logged
            mock_debugger.log_stage_completion.assert_called()

    @pytest.mark.asyncio
    async def test_callback_error_recovery_flow(self):
        """Test callback error recovery flow."""
        # Setup invalid callback
        callback = create_mock_callback_query("item_count:invalid")
        
        state = AsyncMock(spec=FSMContext)
        state.get_data.return_value = {
            'correlation_id': 'test123',
            'query': 'Nike sneakers'
        }
        
        # Mock dependencies
        with patch('bot.handlers.search.search_debugger') as mock_debugger, \
             patch('bot.handlers.search.search_metrics') as mock_metrics, \
             patch('bot.handlers.search._handle_callback_fallback') as mock_fallback:
            
            mock_debugger.create_correlation_id.return_value = 'test123'
            
            # Execute
            await handle_item_count_selection(callback, state)
            
            # Verify fallback was called
            mock_fallback.assert_called_once()
            
            # Verify error was logged
            mock_debugger.log_search_error.assert_called()
            mock_metrics.record_callback_operation.assert_called()

    @pytest.mark.asyncio
    async def test_callback_state_recovery_flow(self):
        """Test callback handling when state is corrupted."""
        # Setup callback with missing query in state
        callback = create_mock_callback_query("item_count:5")
        
        state = AsyncMock(spec=FSMContext)
        state.get_data.return_value = {
            'correlation_id': 'test123'
            # Missing 'query'
        }
        
        # Mock dependencies
        with patch('bot.handlers.search.search_debugger') as mock_debugger, \
             patch('bot.handlers.search.search_metrics') as mock_metrics, \
             patch('bot.handlers.search._handle_callback_fallback') as mock_fallback:
            
            mock_debugger.create_correlation_id.return_value = 'test123'
            
            # Execute
            await handle_item_count_selection(callback, state)
            
            # Verify fallback was called with state clearing
            mock_fallback.assert_called_once()
            args, kwargs = mock_fallback.call_args
            assert kwargs.get('clear_state') is True
            
            # Verify error was logged
            mock_debugger.log_search_error.assert_called()

    @pytest.mark.asyncio
    async def test_custom_count_callback_flow(self):
        """Test custom count selection callback flow."""
        # Setup
        callback = create_mock_callback_query("item_count:custom")
        
        state = AsyncMock(spec=FSMContext)
        state.get_data.return_value = {
            'correlation_id': 'test123',
            'query': 'Nike sneakers'
        }
        
        # Mock dependencies
        with patch('bot.handlers.search.search_debugger') as mock_debugger, \
             patch('bot.handlers.search.search_metrics') as mock_metrics:
            
            mock_debugger.create_correlation_id.return_value = 'test123'
            
            # Execute
            await handle_item_count_selection(callback, state)
            
            # Verify message was edited for custom input
            callback.message.edit_text.assert_called_once()
            edit_args = callback.message.edit_text.call_args[0]
            assert "Введи количество товаров" in edit_args[0]
            
            # Verify state was set to waiting for input
            state.set_state.assert_called_once_with(SearchStates.waiting_for_item_count)
            
            # Verify callback was answered
            callback.answer.assert_called_once_with("✏️ Введи своё количество")
            
            # Verify metrics were recorded
            mock_metrics.record_callback_operation.assert_called()

    @pytest.mark.asyncio
    async def test_callback_logging_and_debugging(self):
        """Test that callback handling includes proper logging and debugging."""
        # Setup
        callback = create_mock_callback_query("item_count:20")
        
        state = AsyncMock(spec=FSMContext)
        state.get_data.return_value = {
            'correlation_id': 'test123',
            'query': 'Vintage jacket'
        }
        
        # Mock dependencies
        with patch('bot.handlers.search.search_debugger') as mock_debugger, \
             patch('bot.handlers.search.search_metrics') as mock_metrics, \
             patch('bot.handlers.search.handle_search_query_with_count') as mock_search, \
             patch('bot.handlers.search.logger') as mock_logger:
            
            mock_debugger.create_correlation_id.return_value = 'test123'
            
            # Execute
            await handle_item_count_selection(callback, state)
            
            # Verify logging occurred
            mock_logger.info.assert_called()
            log_call = mock_logger.info.call_args
            assert "Item count callback received" in log_call[0][0]
            
            # Verify debugging stages were logged
            mock_debugger.log_stage_completion.assert_called()
            
            # Verify metrics were recorded at start and success
            metric_calls = mock_metrics.record_callback_operation.call_args_list
            assert len(metric_calls) >= 2  # At least start and success calls
            
            # Check that correlation_id was used throughout
            debug_calls = mock_debugger.log_stage_completion.call_args_list
            for call in debug_calls:
                args, kwargs = call
                # The correlation_id should be passed in the call
                assert 'test123' in str(call)  # Simple check that correlation_id is used

    @pytest.mark.asyncio
    async def test_callback_boundary_values(self):
        """Test callback handling with boundary values."""
        test_cases = [
            ("item_count:1", True, 1),      # Minimum valid
            ("item_count:100", True, 100),  # Maximum valid
            ("item_count:0", False, None),  # Below minimum
            ("item_count:101", False, None), # Above maximum
        ]
        
        for callback_data, should_succeed, expected_count in test_cases:
            callback = create_mock_callback_query(callback_data)
            
            state = AsyncMock(spec=FSMContext)
            state.get_data.return_value = {
                'correlation_id': 'test123',
                'query': 'Test query'
            }
            
            with patch('bot.handlers.search.search_debugger') as mock_debugger, \
                 patch('bot.handlers.search.search_metrics') as mock_metrics, \
                 patch('bot.handlers.search.handle_search_query_with_count') as mock_search, \
                 patch('bot.handlers.search._handle_callback_fallback') as mock_fallback:
                
                mock_debugger.create_correlation_id.return_value = 'test123'
                
                # Execute
                await handle_item_count_selection(callback, state)
                
                if should_succeed:
                    # Should call search with expected count
                    mock_search.assert_called_once()
                    args = mock_search.call_args[0]
                    assert args[2] == expected_count  # item_count parameter
                    
                    # Should not call fallback
                    mock_fallback.assert_not_called()
                else:
                    # Should call fallback for invalid values
                    mock_fallback.assert_called_once()
                    
                    # Should not call search
                    mock_search.assert_not_called()
                
                # Reset mocks for next iteration
                mock_search.reset_mock()
                mock_fallback.reset_mock()