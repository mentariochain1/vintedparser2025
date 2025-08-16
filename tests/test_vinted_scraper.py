"""Tests for the Vinted scraper module."""
import pytest
from unittest.mock import Mock, patch
from src.bot.services.vinted_scraper import SimpleVintedScraper
from src.bot.services.vinted_scraper.config import DEFAULT_DOMAIN


class TestSimpleVintedScraper:
    """Test the SimpleVintedScraper class."""
    
    def test_init_with_defaults(self):
        """Test scraper initialization with default values."""
        scraper = SimpleVintedScraper()
        assert scraper.base_url == DEFAULT_DOMAIN.rstrip("/")
        assert scraper.session_manager is not None
    
    def test_init_with_custom_params(self):
        """Test scraper initialization with custom parameters."""
        custom_url = "https://www.vinted.com"
        scraper = SimpleVintedScraper(
            base_url=custom_url,
            mobile=True,
            verify_ssl=False
        )
        assert scraper.base_url == custom_url
        assert scraper.session_manager.mobile is True
        assert scraper.session_manager.verify_ssl is False
    
    def test_search_empty_query(self):
        """Test search with empty query returns empty list."""
        scraper = SimpleVintedScraper()
        result = scraper.search("")
        assert result == []
        
        result = scraper.search("   ")
        assert result == []
    
    @patch('src.bot.services.vinted_scraper.scraper.SessionManager')
    def test_search_with_mock_response(self, mock_session_manager):
        """Test search with mocked successful response."""
        # Mock response data
        mock_response = Mock()
        mock_response.json.return_value = {
            "items": [
                {
                    "id": 123456,
                    "title": "Test Item",
                    "price": {"amount": 25.0, "currency_code": "EUR"},
                    "path": "/items/123456-test-item"
                }
            ]
        }
        
        # Mock session manager
        mock_manager_instance = Mock()
        mock_manager_instance.make_request.return_value = mock_response
        mock_session_manager.return_value = mock_manager_instance
        
        scraper = SimpleVintedScraper()
        results = scraper.search("test")
        
        assert len(results) == 1
        assert results[0]["id"] == 123456
        assert results[0]["title"] == "Test Item"
        assert "url" in results[0]
    
    @patch('src.bot.services.vinted_scraper.scraper.SessionManager')
    def test_search_with_failed_response(self, mock_session_manager):
        """Test search with failed response returns mock data."""
        # Mock failed response
        mock_manager_instance = Mock()
        mock_manager_instance.make_request.return_value = None
        mock_session_manager.return_value = mock_manager_instance
        
        scraper = SimpleVintedScraper()
        results = scraper.search("nike")
        
        # Should return mock data
        assert len(results) >= 3
        assert all("_mock" in item for item in results)
        assert all("url" in item for item in results)
    
    def test_search_items_alias(self):
        """Test that search_items is an alias for search."""
        scraper = SimpleVintedScraper()
        
        # Both methods should return the same result
        result1 = scraper.search("test")
        result2 = scraper.search_items("test")
        
        # Since we're using mock data, results should be similar structure
        assert len(result1) == len(result2)
        assert all("_mock" in item for item in result1)
        assert all("_mock" in item for item in result2)
    
    def test_context_manager(self):
        """Test scraper as context manager."""
        with SimpleVintedScraper() as scraper:
            assert scraper is not None
            results = scraper.search("test")
            assert isinstance(results, list)
        
        # After context exit, scraper should be closed
        # (We can't easily test this without mocking, but the structure is correct)
    
    def test_close_method(self):
        """Test close method."""
        scraper = SimpleVintedScraper()
        # Should not raise any exceptions
        scraper.close()


class TestVintedScraperIntegration:
    """Integration tests for the scraper components."""
    
    def test_param_validation(self):
        """Test parameter validation and normalization."""
        from src.bot.services.vinted_scraper.param_utils import validate_search_params
        
        # Test normalization
        text, per_page = validate_search_params("  nike  ", 200, 96)
        assert text == "nike"
        assert per_page == 96  # Should be capped at max
    
    def test_url_enrichment(self):
        """Test URL enrichment functionality."""
        from src.bot.services.vinted_scraper.url_utils import enrich_single_item
        
        item = {"id": 123, "path": "/items/123-test"}
        base_url = "https://www.vinted.at"
        
        enriched = enrich_single_item(item, base_url)
        assert enriched["url"] == "https://www.vinted.at/items/123-test"
    
    def test_mock_data_generation(self):
        """Test mock data generation."""
        from src.bot.services.vinted_scraper.mock_generator import create_mock_results
        
        results = create_mock_results("nike", "https://www.vinted.at")
        
        assert len(results) >= 3
        assert all("id" in item for item in results)
        assert all("title" in item for item in results)
        assert all("url" in item for item in results)
        assert all("_mock" in item for item in results)
        
        # Check Nike-specific items
        nike_titles = [item["title"] for item in results]
        assert any("Nike" in title for title in nike_titles)


@pytest.fixture
def scraper():
    """Fixture providing a scraper instance."""
    return SimpleVintedScraper(verify_ssl=False)


def test_scraper_fixture(scraper):
    """Test the scraper fixture."""
    assert scraper is not None
    assert isinstance(scraper, SimpleVintedScraper)