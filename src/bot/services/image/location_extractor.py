"""Location extraction utilities for Vinted items."""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class LocationExtractor:
    """Extract location information from Vinted item data."""

    @staticmethod
    def extract_location(item: Dict[str, Any]) -> Optional[str]:
        """
        Extract location information from Vinted item data.
        
        Args:
            item: Vinted item dictionary
            
        Returns:
            Location string or None if not found
        """
        try:
            user_info = item.get('user', {})
            if not isinstance(user_info, dict):
                return None
                
            # Primary: city field
            location = user_info.get('city', '')
            if location:
                return location
                
            # Secondary fallbacks for different API structures
            location = user_info.get('location', '')
            if location:
                return location
                
            location = user_info.get('country', '')
            if location:
                return location
                
            # Try nested location object
            location_obj = user_info.get('location_obj', {})
            if isinstance(location_obj, dict):
                location = location_obj.get('city', '') or location_obj.get('name', '')
                if location:
                    return location
                    
            # Final fallback: country code
            country_code = user_info.get('country_code', '')
            if country_code:
                return country_code.upper()
                
            return None
            
        except Exception as e:
            logger.error(f"Error extracting location from item: {e}")
            return None

    @staticmethod
    def format_location_display(location: Optional[str]) -> str:
        """
        Format location for display in messages.
        
        Args:
            location: Location string or None
            
        Returns:
            Formatted location display string
        """
        if location and location.strip():
            return f"📍 Местоположение: {location.strip()}"
        else:
            return "📍 Местоположение: Не указано"

# Global instance
_location_extractor = None

def get_location_extractor() -> LocationExtractor:
    """Get global location extractor instance."""
    global _location_extractor
    if _location_extractor is None:
        _location_extractor = LocationExtractor()
    return _location_extractor

def extract_item_location(item: Dict[str, Any]) -> Optional[str]:
    """Convenience function to extract location from item."""
    extractor = get_location_extractor()
    return extractor.extract_location(item)

def format_location_for_display(location: Optional[str]) -> str:
    """Convenience function to format location for display."""
    extractor = get_location_extractor()
    return extractor.format_location_display(location)
