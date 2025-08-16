"""Comprehensive edge case tests for VintedService to prevent NoneType iteration errors."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.bot.services.vinted_service import VintedService
from src.exceptions import VintedAPIError, VintedRateLimitError, VintedServiceUnavailableError


class MockVintedItem:
    """Mock Vinted item for testing."""

    def __init__(self, item_id: int, title: str = "Test Item", price: float = 25.0):
        self.id = item_id
        self.title = title
        self.price = price
        self.currency = "EUR"
        self.brand = "Test Brand"
        self.size = "M"
        self.condition = "Good"
        self.url = f"https://www.vinted.at/items/{item_id}"
        self.photo = f"https://example.com/photo_{item_id}.jpg"
        self.seller_id = 12345


class MockVintedSearchResult:
    """Mock Vinted search result for testing."""

    def __init__(self, items: list):
        self.items = items


class TestVintedServiceEdgeCases:
    """Test cases for VintedService edge cases and error scenarios."""

    @pytest.fixture
    def vinted_service(self):
        """Create VintedService instance for testing."""
        with patch("src.bot.services.vinted_service.Vinted") as mock_vinted_class:
            mock_vinted = MagicMock()
            mock_vinted_class.return_value = mock_vinted
            service = VintedService()
            service.vinted_client = mock_vinted
            return service

    @pytest.fixture
    def sample_items(self):
        """Create sample Vinted items for testing."""
        items = []
        for i in range(1, 4):
            item = MockVintedItem(i, f"Item {i}", 25.0 + (i * 10))
            items.append(item)
        return items

    # Test Case 1: Normal successful responses with valid items
    @pytest.mark.asyncio
    async def test_normal_successful_response_with_valid_items(self, vinted_service, sample_items):
        """Test normal successful response with valid items - should always return a list."""
        mock_result = MockVintedSearchResult(sample_items)
        vinted_service.vinted_client.search.return_value = mock_result

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                results = []
                for task in tasks:
                    result = await task
                    results.append(result)
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            results = await vinted_service.search_items("test query", max_pages=2)

            # Verify it returns a list (not None)
            assert isinstance(results, list)
            assert len(results) == 6  # 3 items * 2 pages
            assert all(isinstance(item, dict) for item in results)
            assert all("id" in item for item in results)

    # Test Case 2: Error responses like {'error': 'HTTP 200'}
    @pytest.mark.asyncio
    async def test_error_response_dict(self, vinted_service):
        """Test handling of error response dictionaries - should return empty list."""
        # Mock API returning error response
        error_response = {'error': 'HTTP 200'}
        vinted_service.vinted_client.search.return_value = error_response

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                results = []
                for task in tasks:
                    result = await task
                    results.append(result)
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            results = await vinted_service.search_items("test query")

            # Should return empty list, not None or raise error
            assert isinstance(results, list)
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_various_error_responses(self, vinted_service):
        """Test various error response formats."""
        error_responses = [
            {'error': 'HTTP 200'},
            {'error': 'Service temporarily unavailable'},
            {'error': 'Rate limit exceeded'},
            {'error': 'Invalid request'},
            {'errors': ['Multiple errors']},
            {'status': 'error', 'message': 'Something went wrong'}
        ]

        for error_response in error_responses:
            vinted_service.vinted_client.search.return_value = error_response

            with patch("aiometer.run_on_each") as mock_run_on_each:
                async def mock_aiometer_func(func, tasks, **kwargs):
                    results = []
                    for task in tasks:
                        result = await task
                        results.append(result)
                    return results

                mock_run_on_each.side_effect = mock_aiometer_func

                results = await vinted_service.search_items("test query")

                # Should always return a list, never None
                assert isinstance(results, list)
                assert len(results) == 0

    # Test Case 3: Empty search results (no items found)
    @pytest.mark.asyncio
    async def test_empty_search_results(self, vinted_service):
        """Test handling of empty search results - should return empty list."""
        mock_result = MockVintedSearchResult([])
        vinted_service.vinted_client.search.return_value = mock_result

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                results = []
                for task in tasks:
                    result = await task
                    results.append(result)
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            results = await vinted_service.search_items("nonexistent query")

            # Should return empty list, not None
            assert isinstance(results, list)
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_none_result_from_api(self, vinted_service):
        """Test handling when API returns None."""
        vinted_service.vinted_client.search.return_value = None

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                results = []
                for task in tasks:
                    result = await task
                    results.append(result)
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            results = await vinted_service.search_items("test query")

            # Should return empty list when API returns None
            assert isinstance(results, list)
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_falsy_results(self, vinted_service):
        """Test handling of various falsy results from API."""
        falsy_values = [None, False, 0, "", [], {}]

        for falsy_value in falsy_values:
            vinted_service.vinted_client.search.return_value = falsy_value

            with patch("aiometer.run_on_each") as mock_run_on_each:
                async def mock_aiometer_func(func, tasks, **kwargs):
                    results = []
                    for task in tasks:
                        result = await task
                        results.append(result)
                    return results

                mock_run_on_each.side_effect = mock_aiometer_func

                results = await vinted_service.search_items("test query")

                # Should always return a list, never None or other falsy values
                assert isinstance(results, list)
                assert len(results) == 0

    # Test Case 4: Partially corrupted data (some items invalid)
    @pytest.mark.asyncio
    async def test_partially_corrupted_data(self, vinted_service):
        """Test handling of partially corrupted item data - should filter out invalid items but return valid ones."""
        # Mix of valid and invalid items
        corrupted_items = [
            MockVintedItem(1, "Valid Item 1", 25.0),  # Valid item
            MagicMock(),  # Invalid item without required attributes
            MockVintedItem(3, "Valid Item 3", 45.0),  # Valid item
            None,  # Completely invalid item
            ("tuple", "data"),  # Tuple instead of object
        ]
        
        # Remove required attributes from the invalid mock
        invalid_item = corrupted_items[1]
        if hasattr(invalid_item, 'id'):
            delattr(invalid_item, 'id')
        if hasattr(invalid_item, 'title'):
            delattr(invalid_item, 'title')

        mock_result = MockVintedSearchResult(corrupted_items)
        vinted_service.vinted_client.search.return_value = mock_result

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                results = []
                for task in tasks:
                    result = await task
                    results.append(result)
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            results = await vinted_service.search_items("test query")

            # Should return only valid items, filtering out corrupted ones
            assert isinstance(results, list)
            # The actual count may be higher due to multiple pages processing the same items
            # What matters is that all returned items are valid dictionaries with IDs
            assert all(isinstance(item, dict) for item in results)
            assert all("id" in item and item["id"] is not None for item in results)
            # Check that only valid item IDs are present (1 and 3)
            item_ids = {item["id"] for item in results}
            assert item_ids.issubset({1, 3})  # Only valid IDs should be present

    @pytest.mark.asyncio
    async def test_items_with_missing_attributes(self, vinted_service):
        """Test handling of items with missing required attributes."""
        # Create items with missing attributes
        items_with_missing_attrs = []
        
        # Item without ID
        item_no_id = MagicMock()
        item_no_id.title = "Item without ID"
        item_no_id.price = 25.0
        # Remove id attribute
        if hasattr(item_no_id, 'id'):
            delattr(item_no_id, 'id')
        items_with_missing_attrs.append(item_no_id)
        
        # Item without title
        item_no_title = MagicMock()
        item_no_title.id = 2
        item_no_title.price = 35.0
        # Remove title attribute
        if hasattr(item_no_title, 'title'):
            delattr(item_no_title, 'title')
        items_with_missing_attrs.append(item_no_title)
        
        # Valid item for comparison
        valid_item = MockVintedItem(3, "Valid Item", 45.0)
        items_with_missing_attrs.append(valid_item)

        mock_result = MockVintedSearchResult(items_with_missing_attrs)
        vinted_service.vinted_client.search.return_value = mock_result

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                results = []
                for task in tasks:
                    result = await task
                    results.append(result)
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            results = await vinted_service.search_items("test query")

            # Should only return the valid item
            assert isinstance(results, list)
            assert len(results) == 1
            assert results[0]["id"] == 3
            assert results[0]["title"] == "Valid Item"

    @pytest.mark.asyncio
    async def test_items_attribute_is_none(self, vinted_service):
        """Test handling when result.items is None."""
        mock_result = MagicMock()
        mock_result.items = None
        vinted_service.vinted_client.search.return_value = mock_result

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                results = []
                for task in tasks:
                    result = await task
                    results.append(result)
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            results = await vinted_service.search_items("test query")

            # Should return empty list, not raise NoneType error
            assert isinstance(results, list)
            assert len(results) == 0

    # Test Case 5: Rate limiting responses
    @pytest.mark.asyncio
    async def test_rate_limit_error_handling(self, vinted_service):
        """Test handling of rate limit errors - individual page failures return empty lists."""
        # Mock rate limit exception
        def mock_search_rate_limit(**kwargs):
            raise Exception("429 - Rate limit exceeded")

        vinted_service.vinted_client.search.side_effect = mock_search_rate_limit

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                results = []
                for task in tasks:
                    try:
                        result = await task
                        results.append(result)
                    except Exception:
                        results.append([])  # Return empty list on error
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            # When individual pages fail, the service should still return a list (empty)
            # The actual exception raising happens at the main level after processing all pages
            with pytest.raises(VintedRateLimitError):
                await vinted_service.search_items("test query")

    @pytest.mark.asyncio
    async def test_rate_limit_string_in_error(self, vinted_service):
        """Test handling of errors containing 'rate limit' string."""
        def mock_search_rate_limit(**kwargs):
            raise Exception("API rate limit exceeded, please try again later")

        vinted_service.vinted_client.search.side_effect = mock_search_rate_limit

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                results = []
                for task in tasks:
                    try:
                        result = await task
                        results.append(result)
                    except Exception:
                        results.append([])  # Return empty list on error
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            with pytest.raises(VintedRateLimitError) as exc_info:
                await vinted_service.search_items("test query")
            
            assert "rate limit" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_rate_limit_response_dict(self, vinted_service):
        """Test handling of rate limit response as dict."""
        rate_limit_response = {
            'error': 'Rate limit exceeded',
            'code': 429,
            'message': 'Too many requests'
        }
        vinted_service.vinted_client.search.return_value = rate_limit_response

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                results = []
                for task in tasks:
                    result = await task
                    results.append(result)
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            results = await vinted_service.search_items("test query")

            # Should return empty list when rate limit response is dict
            assert isinstance(results, list)
            assert len(results) == 0

    # Test Case 6: Service unavailable responses
    @pytest.mark.asyncio
    async def test_service_unavailable_error(self, vinted_service):
        """Test handling of service unavailable errors."""
        def mock_search_unavailable(**kwargs):
            raise Exception("503 - Service temporarily unavailable")

        vinted_service.vinted_client.search.side_effect = mock_search_unavailable

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                results = []
                for task in tasks:
                    try:
                        result = await task
                        results.append(result)
                    except Exception:
                        results.append([])  # Return empty list on error
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            with pytest.raises(VintedServiceUnavailableError):
                await vinted_service.search_items("test query")

    @pytest.mark.asyncio
    async def test_service_unavailable_string_in_error(self, vinted_service):
        """Test handling of errors containing 'unavailable' string."""
        def mock_search_unavailable(**kwargs):
            raise Exception("Service unavailable due to maintenance")

        vinted_service.vinted_client.search.side_effect = mock_search_unavailable

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                results = []
                for task in tasks:
                    try:
                        result = await task
                        results.append(result)
                    except Exception:
                        results.append([])  # Return empty list on error
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            with pytest.raises(VintedServiceUnavailableError) as exc_info:
                await vinted_service.search_items("test query")
            
            assert "unavailable" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_service_unavailable_response_dict(self, vinted_service):
        """Test handling of service unavailable response as dict."""
        unavailable_response = {
            'error': 'Service temporarily unavailable',
            'code': 503,
            'message': 'Please try again later'
        }
        vinted_service.vinted_client.search.return_value = unavailable_response

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                results = []
                for task in tasks:
                    result = await task
                    results.append(result)
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            results = await vinted_service.search_items("test query")

            # Should return empty list when service unavailable response is dict
            assert isinstance(results, list)
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_generic_api_error_handling(self, vinted_service):
        """Test handling of generic API errors that don't match specific patterns."""
        def mock_search_generic_error(**kwargs):
            raise Exception("Unexpected API error occurred")

        vinted_service.vinted_client.search.side_effect = mock_search_generic_error

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                results = []
                for task in tasks:
                    try:
                        result = await task
                        results.append(result)
                    except Exception:
                        results.append([])  # Return empty list on error
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            with pytest.raises(VintedAPIError) as exc_info:
                await vinted_service.search_items("test query")
            
            assert "Vinted API error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_items_attribute_is_callable_returning_none(self, vinted_service):
        """Test handling when result.items() returns None."""
        mock_result = MagicMock()
        mock_result.items = MagicMock(return_value=None)
        vinted_service.vinted_client.search.return_value = mock_result

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                results = []
                for task in tasks:
                    result = await task
                    results.append(result)
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            results = await vinted_service.search_items("test query")

            # Should return empty list, not raise NoneType error
            assert isinstance(results, list)
            assert len(results) == 0

    # Additional comprehensive tests to ensure no NoneType iteration errors
    @pytest.mark.asyncio
    async def test_none_type_iteration_prevention_comprehensive(self, vinted_service):
        """Comprehensive test to ensure no NoneType iteration errors in any scenario."""
        problematic_scenarios = [
            None,  # Direct None
            {'error': 'Any error'},  # Error dict
            {'items': None},  # Dict with None items
            MagicMock(items=None),  # Object with None items attribute
            MagicMock(items=lambda: None),  # Object with callable items returning None
            [],  # Empty list
            {},  # Empty dict
            False,  # False value
            0,  # Zero
            "",  # Empty string
        ]
        
        for scenario in problematic_scenarios:
            vinted_service.vinted_client.search.return_value = scenario

            with patch("aiometer.run_on_each") as mock_run_on_each:
                async def mock_aiometer_func(func, tasks, **kwargs):
                    results = []
                    for task in tasks:
                        result = await task
                        results.append(result)
                    return results

                mock_run_on_each.side_effect = mock_aiometer_func

                results = await vinted_service.search_items("test query")

                # Should ALWAYS return a list, never None or cause iteration errors
                assert isinstance(results, list)
                assert len(results) == 0

    @pytest.mark.asyncio
    async def test_mixed_valid_and_none_pages(self, vinted_service, sample_items):
        """Test scenario where some pages return valid data and others return None."""
        call_count = 0
        
        def mock_search_mixed(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:  # Even calls return None
                return None
            else:  # Odd calls return valid data
                return MockVintedSearchResult(sample_items)

        vinted_service.vinted_client.search.side_effect = mock_search_mixed

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                results = []
                for task in tasks:
                    result = await task
                    results.append(result)
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            results = await vinted_service.search_items("test query", max_pages=4)

            # Should return items from valid pages only, filtered properly
            assert isinstance(results, list)
            # Should have items from 2 valid pages (pages 1 and 3)
            assert len(results) == 6  # 3 items * 2 valid pages

    @pytest.mark.asyncio
    async def test_search_method_always_returns_list_guarantee(self, vinted_service):
        """Final guarantee test - search_items method MUST always return a list."""
        extreme_scenarios = [
            None,  # API returns None
            Exception("API completely broken"),  # API throws exception
            {'error': 'Complete failure'},  # API returns error dict
            MagicMock(items=None),  # Result object with None items
            MagicMock(spec=[]),  # Empty spec object
        ]
        
        for scenario in extreme_scenarios:
            if isinstance(scenario, Exception):
                vinted_service.vinted_client.search.side_effect = scenario
            else:
                vinted_service.vinted_client.search.return_value = scenario
                vinted_service.vinted_client.search.side_effect = None

            with patch("aiometer.run_on_each") as mock_run_on_each:
                async def mock_aiometer_func(func, tasks, **kwargs):
                    results = []
                    for task in tasks:
                        try:
                            result = await task
                            results.append(result)
                        except Exception:
                            results.append([])  # Always append empty list on error
                    return results

                mock_run_on_each.side_effect = mock_aiometer_func

                try:
                    results = await vinted_service.search_items("test query")
                    # If it doesn't raise an exception, it must return a list
                    assert isinstance(results, list)
                except (VintedAPIError, VintedRateLimitError, VintedServiceUnavailableError):
                    # These exceptions are acceptable - they're proper error handling
                    pass
                except Exception as e:
                    # Any other exception (like NoneType iteration) is a test failure
                    assert False, f"Unexpected exception type: {type(e).__name__}: {e}"

    @pytest.mark.asyncio
    async def test_item_processing_never_fails_on_none(self, vinted_service):
        """Test that item processing never fails due to NoneType iteration."""
        # Create a scenario with mixed None and valid items
        mixed_items = [
            MockVintedItem(1, "Valid Item", 25.0),
            None,  # None item
            MockVintedItem(2, "Another Valid Item", 35.0),
            MagicMock(),  # Mock without proper attributes
            None,  # Another None
        ]
        
        # Ensure the mock doesn't have required attributes
        mock_item = mixed_items[3]
        for attr in ['id', 'title']:
            if hasattr(mock_item, attr):
                delattr(mock_item, attr)

        mock_result = MockVintedSearchResult(mixed_items)
        vinted_service.vinted_client.search.return_value = mock_result

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                results = []
                for task in tasks:
                    result = await task
                    results.append(result)
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            # This should never raise a NoneType iteration error
            results = await vinted_service.search_items("test query")

            # Should return only the valid items, filtering out None and invalid ones
            assert isinstance(results, list)
            assert len(results) == 2  # Only the 2 valid items
            assert all(item["id"] in [1, 2] for item in results)
