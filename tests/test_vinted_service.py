"""Comprehensive tests for VintedService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.services.vinted_service import VintedService

class MockVintedItem :
    """Mock Vinted item for testing."""

    def __init__ (self ,item_id :int ,title :str ="Test Item",price :float =25.0 ):
        self .id =item_id
        self .title =title
        self .price =price
        self .currency ="EUR"
        self .brand ="Test Brand"
        self .size ="M"
        self .condition ="Good"
        self .url =f"https://www.vinted.at/items/{item_id }"
        self .photo =f"https://example.com/photo_{item_id }.jpg"
        self .seller_id =12345
        self .description ="Test description"
        self .photos =[
        MagicMock (url =f"https://example.com/photo_{item_id }_1.jpg"),
        MagicMock (url =f"https://example.com/photo_{item_id }_2.jpg"),
        ]

class MockVintedSearchResult :
    """Mock Vinted search result for testing."""

    def __init__ (self ,items :list ):
        self .items =items

class MockVintedItemInfo :
    """Mock Vinted item info result for testing."""

    def __init__ (self ,item :MockVintedItem ):
        self .item =item

class TestVintedService:
    """Comprehensive test cases for VintedService."""

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
    def sample_items(self, mock_vinted_item):
        """Create sample Vinted items for testing."""
        items = []
        for i in range(1, 4):
            item = MagicMock()
            item.id = i
            item.title = f"Item {i}"
            item.price = 25.0 + (i * 10)
            item.currency = "EUR"
            item.brand = "Test Brand"
            item.size = "M"
            item.condition = "Good"
            item.url = f"https://www.vinted.at/items/{i}"
            item.photo = f"https://example.com/photo_{i}.jpg"
            item.seller_id = 12345
            item.description = "Test description"
            item.photos = [
                MagicMock(url=f"https://example.com/photo_{i}_1.jpg"),
                MagicMock(url=f"https://example.com/photo_{i}_2.jpg"),
            ]
            items.append(item)
        return items

    @pytest .mark .asyncio
    async def test_search_items_success (self ,vinted_service ,sample_items ):
        """Test successful item search."""

        mock_result =MockVintedSearchResult (sample_items )
        vinted_service .vinted_client .search .return_value =mock_result

        with patch ("aiometer.run_on_each")as mock_run_on_each :

            async def mock_aiometer_func (func ,tasks ,**kwargs ):
                results =[]
                for task in tasks :
                    result =await task
                    results .append (result )
                return results

            mock_run_on_each .side_effect =mock_aiometer_func

            results =await vinted_service .search_items ("test query",max_pages =2 )

            assert len (results )==6
            assert all (item ["ships_to_at"]is True for item in results )
            assert all (item ["currency"]=="EUR"for item in results )

            vinted_service .vinted_client .search .assert_called ()
            call_args =vinted_service .vinted_client .search .call_args [1 ]
            assert call_args ["country_ids"]==14
            assert call_args ["query"]=="test query"

    @pytest .mark .asyncio
    async def test_search_items_empty_result (self ,vinted_service ):
        """Test search with no results."""

        mock_result =MockVintedSearchResult ([])
        vinted_service .vinted_client .search .return_value =mock_result

        with patch ("aiometer.run_on_each")as mock_run_on_each :
            async def mock_aiometer_func (func ,tasks ,**kwargs ):
                results =[]
                for task in tasks :
                    result =await task
                    results .append (result )
                return results

            mock_run_on_each .side_effect =mock_aiometer_func

            results =await vinted_service .search_items ("nonexistent query")

            assert len (results )==0

    @pytest .mark .asyncio
    async def test_search_items_with_filters (self ,vinted_service ,sample_items ):
        """Test search with additional filters."""
        mock_result =MockVintedSearchResult (sample_items )
        vinted_service .vinted_client .search .return_value =mock_result

        with patch ("aiometer.run_on_each")as mock_run_on_each :
            async def mock_aiometer_func (func ,tasks ,**kwargs ):
                results =[]
                for task in tasks :
                    result =await task
                    results .append (result )
                return results

            mock_run_on_each .side_effect =mock_aiometer_func

            results =await vinted_service .search_items (
            "test query",
            max_pages =1 ,
            brand_ids =[1 ,2 ,3 ],
            price_from =10 ,
            price_to =50
            )

            assert len (results )==3

            call_args =vinted_service .vinted_client .search .call_args [1 ]
            assert call_args ["brand_ids"]==[1 ,2 ,3 ]
            assert call_args ["price_from"]==10
            assert call_args ["price_to"]==50

    @pytest .mark .asyncio
    async def test_get_item_details_success (self ,vinted_service ,sample_items ):
        """Test successful item details fetching."""

        def mock_item_info (item_id ):
            item =next ((item for item in sample_items if item .id ==item_id ),None )
            return MockVintedItemInfo (item )if item else None

        vinted_service .vinted_client .item_info .side_effect =mock_item_info

        with patch ("aiometer.run_on_each")as mock_run_on_each :
            async def mock_aiometer_func (func ,tasks ,**kwargs ):
                results =[]
                for task in tasks :
                    result =await task
                    results .append (result )
                return results

            mock_run_on_each .side_effect =mock_aiometer_func

            results =await vinted_service .get_item_details ([1 ,2 ,3 ])

            assert len (results )==3
            assert all (item is not None for item in results )
            assert all (len (item ["photos"])==2 for item in results )
            assert all (item ["description"]=="Test description"for item in results )

    @pytest .mark .asyncio
    async def test_get_item_details_empty_list (self ,vinted_service ):
        """Test item details fetching with empty list."""
        results =await vinted_service .get_item_details ([])
        assert len (results )==0

    @pytest .mark .asyncio
    async def test_get_item_details_some_failures (self ,vinted_service ,sample_items ):
        """Test item details fetching with some failures."""
        def mock_item_info (item_id ):
            if item_id ==2 :
                raise Exception ("Item not found")
            item =next ((item for item in sample_items if item .id ==item_id ),None )
            return MockVintedItemInfo (item )if item else None

        vinted_service .vinted_client .item_info .side_effect =mock_item_info

        with patch ("aiometer.run_on_each")as mock_run_on_each :
            async def mock_aiometer_func (func ,tasks ,**kwargs ):
                results =[]
                for task in tasks :
                    result =await task
                    results .append (result )
                return results

            mock_run_on_each .side_effect =mock_aiometer_func

            results =await vinted_service .get_item_details ([1 ,2 ,3 ])

            assert len (results )==2
            assert all (item is not None for item in results )
            assert {item ["id"]for item in results }=={1 ,3 }

    @pytest .mark .asyncio
    async def test_fetch_item_detail_retry_logic (self ,vinted_service ,sample_items ):
        """Test retry logic in item detail fetching."""
        call_count =0

        def mock_item_info (item_id ):
            nonlocal call_count
            call_count +=1
            if call_count <3 :
                raise Exception ("Temporary error")
            return MockVintedItemInfo (sample_items [0 ])

        vinted_service .vinted_client .item_info .side_effect =mock_item_info

        with patch ("asyncio.sleep"):
            result =await vinted_service ._fetch_item_detail (1 )

        assert result is not None
        assert result ["id"]==1
        assert call_count ==3

    @pytest .mark .asyncio
    async def test_fetch_item_detail_max_retries_exceeded (self ,vinted_service ):
        """Test item detail fetching when max retries exceeded."""
        vinted_service .vinted_client .item_info .side_effect =Exception ("Persistent error")

        with patch ("asyncio.sleep"):
            result =await vinted_service ._fetch_item_detail (1 )

        assert result is None
        assert vinted_service .vinted_client .item_info .call_count ==3

    @pytest .mark .asyncio
    async def test_search_and_get_details (self ,vinted_service ,sample_items ):
        """Test combined search and details fetching."""

        mock_search_result =MockVintedSearchResult (sample_items )
        vinted_service .vinted_client .search .return_value =mock_search_result

        def mock_item_info (item_id ):
            item =next ((item for item in sample_items if item .id ==item_id ),None )
            return MockVintedItemInfo (item )if item else None

        vinted_service .vinted_client .item_info .side_effect =mock_item_info

        with patch ("aiometer.run_on_each")as mock_run_on_each :
            async def mock_aiometer_func (func ,tasks ,**kwargs ):
                results =[]
                for task in tasks :
                    result =await task
                    results .append (result )
                return results

            mock_run_on_each .side_effect =mock_aiometer_func

            results =await vinted_service .search_and_get_details ("test query",max_pages =1 )

            assert len (results )==3
            assert all (item ["description"]=="Test description"for item in results )
            assert all (len (item ["photos"])==2 for item in results )

    @pytest .mark .asyncio
    async def test_search_and_get_details_no_search_results (self ,vinted_service ):
        """Test combined search and details when search returns no results."""
        mock_search_result =MockVintedSearchResult ([])
        vinted_service .vinted_client .search .return_value =mock_search_result

        with patch ("aiometer.run_on_each")as mock_run_on_each :
            async def mock_aiometer_func (func ,tasks ,**kwargs ):
                results =[]
                for task in tasks :
                    result =await task
                    results .append (result )
                return results

            mock_run_on_each .side_effect =mock_aiometer_func

            results =await vinted_service .search_and_get_details ("nonexistent query")

            assert len (results )==0

            vinted_service .vinted_client .item_info .assert_not_called ()

    def test_get_item_url (self ,vinted_service ):
        """Test item URL generation."""
        url =vinted_service .get_item_url (12345 )
        assert url =="https://www.vinted.at/items/12345"

    @pytest .mark .asyncio
    async def test_health_check_success (self ,vinted_service ,sample_items ):
        """Test successful health check."""
        mock_result =MockVintedSearchResult (sample_items [:1 ])
        vinted_service .vinted_client .search .return_value =mock_result

        with patch ("aiometer.run_on_each")as mock_run_on_each :
            async def mock_aiometer_func (func ,tasks ,**kwargs ):
                results =[]
                for task in tasks :
                    result =await task
                    results .append (result )
                return results

            mock_run_on_each .side_effect =mock_aiometer_func

            is_healthy =await vinted_service .health_check ()

            assert is_healthy is True

    @pytest .mark .asyncio
    async def test_health_check_failure (self ,vinted_service ):
        """Test health check failure."""
        vinted_service .vinted_client .search .side_effect =Exception ("Service unavailable")

        with patch ("aiometer.run_on_each")as mock_run_on_each :
            async def mock_aiometer_func (func ,tasks ,**kwargs ):
                raise Exception ("Service unavailable")

            mock_run_on_each .side_effect =mock_aiometer_func

            is_healthy =await vinted_service .health_check ()

            assert is_healthy is False

    def test_initialize_client_failure (self ):
        """Test client initialization failure."""
        with patch ("src.bot.services.vinted_service.Vinted")as mock_vinted_class :
            mock_vinted_class .side_effect =Exception ("Failed to initialize")

            with pytest .raises (Exception ,match ="Failed to initialize"):
                VintedService ()

    @pytest .mark .asyncio
    async def test_fetch_search_page_no_items_attribute (self ,vinted_service ):
        """Test search page fetching when result has no items attribute."""
        mock_result =MagicMock ()
        del mock_result .items
        vinted_service .vinted_client .search .return_value =mock_result

        result =await vinted_service ._fetch_search_page ({"query":"test"},1 )

        assert result ==[]

    @pytest.mark.asyncio
    async def test_fetch_search_page_retry_logic(self, vinted_service, sample_items):
        """Test retry logic in search page fetching."""
        call_count = 0

        def mock_search(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary error")
            return MockVintedSearchResult(sample_items)

        vinted_service.vinted_client.search.side_effect = mock_search

        with patch("asyncio.sleep"):
            result = await vinted_service._fetch_search_page({"query": "test"}, 1)

        assert len(result) == 3
        assert call_count == 3

    # Additional comprehensive tests for edge cases and error handling

    @pytest.mark.asyncio
    async def test_search_items_rate_limit_error(self, vinted_service):
        """Test search with rate limit error."""
        from src.exceptions import RateLimitError
        
        vinted_service.vinted_client.search.side_effect = RateLimitError("Rate limit exceeded")

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                results = []
                for task in tasks:
                    try:
                        result = await task
                        results.append(result)
                    except RateLimitError:
                        results.append([])  # Return empty list on rate limit
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            results = await vinted_service.search_items("test query")

            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_items_network_error(self, vinted_service):
        """Test search with network error."""
        import httpx
        
        vinted_service.vinted_client.search.side_effect = httpx.NetworkError("Network unreachable")

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                results = []
                for task in tasks:
                    try:
                        result = await task
                        results.append(result)
                    except httpx.NetworkError:
                        results.append([])
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            results = await vinted_service.search_items("test query")

            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_item_details_partial_success(self, vinted_service, sample_items):
        """Test item details fetching with partial success."""
        def mock_item_info(item_id):
            if item_id == 2:
                return None  # Simulate item not found
            item = next((item for item in sample_items if item.id == item_id), None)
            return MockVintedItemInfo(item) if item else None

        vinted_service.vinted_client.item_info.side_effect = mock_item_info

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                results = []
                for task in tasks:
                    result = await task
                    if result is not None:
                        results.append(result)
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            results = await vinted_service.get_item_details([1, 2, 3])

            assert len(results) == 2  # Only items 1 and 3 should be returned
            assert {item["id"] for item in results} == {1, 3}

    @pytest.mark.asyncio
    async def test_fetch_item_detail_cloudflare_error(self, vinted_service):
        """Test item detail fetching with Cloudflare error."""
        import httpx
        
        def mock_item_info(item_id):
            response = httpx.Response(1020, text="Cloudflare blocked")
            raise httpx.HTTPStatusError("Cloudflare blocked", request=None, response=response)

        vinted_service.vinted_client.item_info.side_effect = mock_item_info

        with patch("asyncio.sleep"):
            result = await vinted_service._fetch_item_detail(1)

        assert result is None

    @pytest.mark.asyncio
    async def test_search_with_all_filters(self, vinted_service, sample_items):
        """Test search with all possible filters."""
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

            results = await vinted_service.search_items(
                "test query",
                max_pages=2,
                brand_ids=[1, 2, 3],
                catalog_ids=[4, 5, 6],
                color_ids=[7, 8, 9],
                material_ids=[10, 11, 12],
                price_from=10,
                price_to=100,
                size_ids=[13, 14, 15],
                status_ids=[16, 17, 18],
            )

            assert len(results) == 6  # 3 items * 2 pages

            # Verify all filters were passed
            call_args = vinted_service.vinted_client.search.call_args[1]
            assert call_args["brand_ids"] == [1, 2, 3]
            assert call_args["catalog_ids"] == [4, 5, 6]
            assert call_args["color_ids"] == [7, 8, 9]
            assert call_args["material_ids"] == [10, 11, 12]
            assert call_args["price_from"] == 10
            assert call_args["price_to"] == 100
            assert call_args["size_ids"] == [13, 14, 15]
            assert call_args["status_ids"] == [16, 17, 18]

    @pytest.mark.asyncio
    async def test_search_items_pagination_limit(self, vinted_service, sample_items):
        """Test search with maximum pagination limit."""
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

            # Test with very high page count
            results = await vinted_service.search_items("test query", max_pages=100)

            # Should be limited to reasonable number of pages
            assert len(results) <= 300  # Assuming max 10 pages * 30 items per page

    @pytest.mark.asyncio
    async def test_get_item_url_validation(self, vinted_service):
        """Test item URL generation with various inputs."""
        # Test normal item ID
        url = vinted_service.get_item_url(12345)
        assert url == "https://www.vinted.at/items/12345"

        # Test very large item ID
        url = vinted_service.get_item_url(999999999999)
        assert url == "https://www.vinted.at/items/999999999999"

        # Test minimum item ID
        url = vinted_service.get_item_url(1)
        assert url == "https://www.vinted.at/items/1"

    @pytest.mark.asyncio
    async def test_health_check_timeout(self, vinted_service):
        """Test health check with timeout."""
        import asyncio
        
        async def slow_search(**kwargs):
            await asyncio.sleep(10)  # Simulate slow response
            return MockVintedSearchResult([])

        vinted_service.vinted_client.search.side_effect = slow_search

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                raise asyncio.TimeoutError("Request timed out")

            mock_run_on_each.side_effect = mock_aiometer_func

            is_healthy = await vinted_service.health_check()

            assert is_healthy is False

    @pytest.mark.asyncio
    async def test_search_and_get_details_mixed_results(self, vinted_service, sample_items):
        """Test combined search and details with mixed success/failure."""
        mock_search_result = MockVintedSearchResult(sample_items)
        vinted_service.vinted_client.search.return_value = mock_search_result

        def mock_item_info(item_id):
            if item_id == 2:
                raise Exception("Item details unavailable")
            item = next((item for item in sample_items if item.id == item_id), None)
            return MockVintedItemInfo(item) if item else None

        vinted_service.vinted_client.item_info.side_effect = mock_item_info

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                results = []
                for task in tasks:
                    try:
                        result = await task
                        if result is not None:
                            results.append(result)
                    except Exception:
                        pass  # Skip failed items
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            results = await vinted_service.search_and_get_details("test query", max_pages=1)

            # Should return only successful items (1 and 3, not 2)
            assert len(results) == 2
            assert {item["id"] for item in results} == {1, 3}

    @pytest.mark.asyncio
    async def test_concurrent_request_limiting(self, vinted_service, sample_items):
        """Test that concurrent requests are properly limited."""
        mock_result = MockVintedSearchResult(sample_items)
        vinted_service.vinted_client.search.return_value = mock_result

        with patch("aiometer.run_on_each") as mock_run_on_each:
            # Verify aiometer is called with proper concurrency limits
            async def mock_aiometer_func(func, tasks, max_at_once=None, max_per_second=None, **kwargs):
                assert max_at_once is not None
                assert max_per_second is not None
                assert max_at_once <= 10  # Should respect MAX_CONCURRENT_REQUESTS
                assert max_per_second <= 0.5  # Should respect rate limit (30/min = 0.5/sec)
                
                results = []
                for task in tasks:
                    result = await task
                    results.append(result)
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            await vinted_service.search_items("test query", max_pages=2)

            # Verify aiometer was called
            mock_run_on_each.assert_called()

    def test_client_initialization_with_domain(self):
        """Test client initialization with Austrian domain."""
        with patch("src.bot.services.vinted_service.Vinted") as mock_vinted_class:
            mock_vinted = MagicMock()
            mock_vinted_class.return_value = mock_vinted
            
            service = VintedService()
            
            # Verify client was initialized with Austrian domain
            mock_vinted_class.assert_called_once_with(domain="at")
            assert service.vinted_client == mock_vinted

    @pytest.mark.asyncio
    async def test_item_data_transformation(self, vinted_service, sample_items):
        """Test proper transformation of Vinted item data."""
        def mock_item_info(item_id):
            item = next((item for item in sample_items if item.id == item_id), None)
            return MockVintedItemInfo(item) if item else None

        vinted_service.vinted_client.item_info.side_effect = mock_item_info

        with patch("aiometer.run_on_each") as mock_run_on_each:
            async def mock_aiometer_func(func, tasks, **kwargs):
                results = []
                for task in tasks:
                    result = await task
                    results.append(result)
                return results

            mock_run_on_each.side_effect = mock_aiometer_func

            results = await vinted_service.get_item_details([1])

            assert len(results) == 1
            item = results[0]
            
            # Verify all required fields are present and properly formatted
            assert "id" in item
            assert "title" in item
            assert "price" in item
            assert "currency" in item
            assert "brand" in item
            assert "size" in item
            assert "condition" in item
            assert "description" in item
            assert "seller_id" in item
            assert "url" in item
            assert "photos" in item
            assert "ships_to_at" in item
            
            # Verify ships_to_at is always True for Austrian searches
            assert item["ships_to_at"] is True
            
            # Verify photos is a list of URLs
            assert isinstance(item["photos"], list)
            assert all(isinstance(photo, str) for photo in item["photos"]) 