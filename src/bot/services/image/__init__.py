"""
Image processing service for Vinted bot.
Provides compact image validation and media group creation.
"""

import requests
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse
from telegram import InputMediaPhoto
from monitoring import get_logger

logger = get_logger(__name__)

class VintedImageProcessor:
    """Compact image processor for Vinted items."""

    def __init__(self, timeout: int = 10):
        """Initialize with timeout settings."""
        self.timeout = timeout
        self.max_images_per_group = 10
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; TelegramBot/1.0)',
            'Accept': 'image/*,*/*;q=0.8'
        })

    def validate_image_url(self, url: str) -> bool:
        """Quick validation for image URLs."""
        if not url or not isinstance(url, str):
            return False

        # Very lenient for Vinted URLs
        if 'vinted' in url.lower():
            try:
                parsed = urlparse(url)
                return bool(parsed.scheme and parsed.netloc)
            except:
                return url.startswith('http')

        # Basic validation for other URLs
        try:
            parsed = urlparse(url)
            if not (parsed.scheme and parsed.netloc):
                return False

            # Check for image-like patterns
            url_lower = url.lower()
            image_indicators = ['.jpg', '.jpeg', '.png', '.gif', '.webp', 'images', 'photos', 'img']
            return any(indicator in url_lower for indicator in image_indicators)

        except Exception:
            return False

    def extract_images_from_item(self, item: Dict[str, Any]) -> List[str]:
        """Extract image URLs from Vinted item data."""
        images = []

        try:
            # Method 1: Pre-processed images
            if '_all_images' in item and isinstance(item['_all_images'], list):
                images.extend(item['_all_images'])

            # Method 2: Photos array
            photos = item.get('photos', [])
            for photo in photos:
                if isinstance(photo, dict):
                    for size_key in ['high_resolution', 'full_size', 'large', 'medium', 'url']:
                        if size_key in photo:
                            size_data = photo[size_key]
                            if isinstance(size_data, dict) and 'url' in size_data:
                                url = size_data['url']
                            elif isinstance(size_data, str):
                                url = size_data
                            else:
                                continue

                            if url and url.startswith('http'):
                                images.append(url)
                                break
                elif isinstance(photo, str) and photo.startswith('http'):
                    images.append(photo)

            # Method 3: Single photo field
            if 'photo' in item:
                photo = item['photo']
                if isinstance(photo, dict) and 'url' in photo:
                    url = photo['url']
                    if url and url.startswith('http'):
                        images.append(url)
                elif isinstance(photo, str) and photo.startswith('http'):
                    images.append(photo)

            # Remove duplicates while preserving order
            seen = set()
            unique_images = []
            for img in images:
                if img not in seen:
                    seen.add(img)
                    unique_images.append(img)

            return unique_images[:self.max_images_per_group]

        except Exception as e:
            logger.error(f"Error extracting images: {str(e)}")
            return []

    def filter_valid_images(self, image_urls: List[str]) -> List[str]:
        """Filter and return only valid image URLs."""
        valid_images = []

        for url in image_urls:
            if self.validate_image_url(url):
                valid_images.append(url)
            else:
                logger.debug(f"Filtered invalid image: {url}")

        logger.info(f"Image filtering: {len(image_urls)} -> {len(valid_images)} valid")
        return valid_images

    def create_media_group(self, images: List[str], caption: str = "") -> Tuple[List[InputMediaPhoto], str]:
        """
        Create Telegram media group with fallback strategies.
        Returns (media_group, fallback_strategy).
        """
        if not images:
            return [], "no_images"

        valid_images = self.filter_valid_images(images)
        if not valid_images:
            return [], "no_valid_images"

        # Progressive fallback strategies
        strategies = [
            (10, "media_group_10"),
            (8, "media_group_8"),
            (5, "media_group_5"),
            (3, "media_group_3"),
            (1, "single_image")
        ]

        for max_count, strategy_name in strategies:
            if len(valid_images) >= (1 if strategy_name == "single_image" else 2):
                try:
                    selected_images = valid_images[:max_count]
                    media_group = []
                    caption_used = False

                    for img_url in selected_images:
                        try:
                            if not caption_used and caption:
                                media_item = InputMediaPhoto(
                                    media=img_url,
                                    caption=caption[:1024],
                                    parse_mode='Markdown'
                                )
                                caption_used = True
                            else:
                                media_item = InputMediaPhoto(media=img_url)

                            media_group.append(media_item)

                        except Exception as e:
                            logger.debug(f"Failed to create media item: {str(e)}")
                            continue

                    # Validate media group size
                    min_required = 1 if strategy_name == "single_image" else 2
                    if len(media_group) >= min_required:
                        logger.info(f"Created media group with {strategy_name}: {len(media_group)} images")
                        return media_group, strategy_name

                except Exception as e:
                    logger.debug(f"Strategy {strategy_name} failed: {str(e)}")
                    continue

        return [], "all_strategies_failed"

    def process_search_results(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process search results and enhance with image data."""
        enhanced_items = []

        for item in items:
            try:
                # Extract and validate images
                raw_images = self.extract_images_from_item(item)
                valid_images = self.filter_valid_images(raw_images)

                # Add image metadata
                item['_processed_images'] = valid_images
                item['_image_count'] = len(valid_images)
                item['_has_images'] = len(valid_images) > 0
                item['_can_send_media_group'] = len(valid_images) > 0

                enhanced_items.append(item)

            except Exception as e:
                logger.error(f"Error processing item images: {str(e)}")
                # Add item with empty image data
                item.update({
                    '_processed_images': [],
                    '_image_count': 0,
                    '_has_images': False,
                    '_can_send_media_group': False
                })
                enhanced_items.append(item)

        total_items = len(enhanced_items)
        items_with_images = sum(1 for item in enhanced_items if item.get('_has_images'))
        logger.info(f"Processed {total_items} items, {items_with_images} have images")

        return enhanced_items

    def close(self):
        """Clean up resources."""
        if self.session:
            self.session.close()

# Global instance
_image_processor = None

def get_image_processor() -> VintedImageProcessor:
    """Get global image processor instance."""
    global _image_processor
    if _image_processor is None:
        _image_processor = VintedImageProcessor()
    return _image_processor

def process_vinted_images(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convenience function to process Vinted search results."""
    processor = get_image_processor()
    return processor.process_search_results(items)

def create_telegram_media_group(images: List[str], caption: str = "") -> Tuple[List[InputMediaPhoto], str]:
    """Convenience function to create Telegram media group."""
    processor = get_image_processor()
    return processor.create_media_group(images, caption)
