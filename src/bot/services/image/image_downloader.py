"""
Image download and caching service for Vinted Telegram bot.
Handles downloading images from URLs and caching them locally for Telegram bot output.
Also provides web scraping capabilities to extract all images from item pages.
"""

import aiohttp
import asyncio
import hashlib
import ssl
from typing import Optional, List, Dict, Any
from pathlib import Path
from urllib.parse import urljoin, urlparse
from src.monitoring import get_logger

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    BeautifulSoup = None

logger = get_logger(__name__)

# Download constants
DOWNLOAD_TIMEOUT = 30
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
CHUNK_SIZE = 8192
CACHE_DIR = Path("/tmp/telegram_image_cache")
CACHE_DIR.mkdir(exist_ok=True)

class ImageDownloader:
    """Downloads images from URLs for local processing."""
    
    def __init__(self):
        """Set up downloader with session."""
        self.session = None
        self.cache_dir = CACHE_DIR
        self.DOWNLOAD_TIMEOUT = DOWNLOAD_TIMEOUT
        self.verify_ssl = True

    def _get_cache_path(self, url: str) -> Path:
        """Generate cache path for URL."""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.cache_dir / f"{url_hash}.jpg"

    def _is_cached(self, url: str) -> bool:
        """Check if image is cached."""
        cache_path = self._get_cache_path(url)
        return cache_path.exists() and cache_path.stat().st_size > 0
        
    def _create_ssl_context(self):
        """Create SSL context based on verification setting."""
        if not self.verify_ssl:
            # Create context that doesn't verify certificates
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            return context
        return None

    def _create_connector(self):
        """Create TCP connector with SSL settings."""
        ssl_context = self._create_ssl_context()
        return aiohttp.TCPConnector(
            limit=10,
            limit_per_host=5,
            ssl=ssl_context
        )

    def _is_ssl_error(self, exception: Exception) -> bool:
        """Check if exception is SSL-related."""
        error_str = str(exception).lower()
        return 'ssl' in error_str or 'certificate' in error_str or 'tls' in error_str

    def _handle_ssl_error(self):
        """Handle SSL error by disabling verification."""
        if self.verify_ssl:
            logger.warning("SSL error detected, switching to no SSL verification")
            self.verify_ssl = False
            return True  # Indicate that we need to retry
        return False  # Already disabled SSL, can't retry

    async def __aenter__(self):
        """Start async session."""
        connector = self._create_connector()
        timeout = aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT)

        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; TelegramBot/1.0)',
                'Accept': 'image/*'
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close async session."""
        if self.session:
            await self.session.close()
            
    async def download_image(self, url: str, save_path: Path, use_cache: bool = True) -> bool:
        """Download single image to file with caching support."""
        if not self.session:
            logger.error("Session not initialized. Use 'async with' context.")
            return False

        # Check cache first
        if use_cache and self._is_cached(url):
            cache_path = self._get_cache_path(url)
            try:
                # Copy from cache to save_path
                with open(cache_path, 'rb') as cache_file:
                    with open(save_path, 'wb') as save_file:
                        save_file.write(cache_file.read())
                logger.info(f"Image loaded from cache: {save_path.name}")
                return True
            except Exception as e:
                logger.warning(f"Failed to load from cache: {e}")

        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.debug(f"Bad response for {url}: {response.status}")
                    return False

                content_length = response.headers.get('Content-Length')
                if content_length and int(content_length) > MAX_FILE_SIZE:
                    logger.debug(f"File too large: {content_length} bytes")
                    return False

                save_path.parent.mkdir(parents=True, exist_ok=True)

                with open(save_path, 'wb') as f:
                    downloaded = 0
                    async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                        downloaded += len(chunk)
                        if downloaded > MAX_FILE_SIZE:
                            logger.debug(f"Download exceeded size limit: {downloaded}")
                            save_path.unlink(missing_ok=True)
                            return False
                        f.write(chunk)

                # Save to cache if caching enabled
                if use_cache:
                    try:
                        cache_path = self._get_cache_path(url)
                        with open(save_path, 'rb') as src_file:
                            with open(cache_path, 'wb') as cache_file:
                                cache_file.write(src_file.read())
                        logger.debug(f"Image cached: {cache_path.name}")
                    except Exception as e:
                        logger.debug(f"Failed to cache image: {e}")

                logger.info(f"Downloaded image: {save_path.name} ({downloaded} bytes)")
                return True

        except Exception as e:
            logger.error(f"Download failed for {url}: {e}")
            save_path.unlink(missing_ok=True)
            return False
            
    async def download_batch(self, urls: List[str], folder: Path) -> List[Path]:
        """Download multiple images to folder."""
        if not self.session:
            logger.error("Session not initialized. Use 'async with' context.")
            return []

        tasks = []
        for i, url in enumerate(urls):
            filename = f"image_{i:03d}.jpg"
            save_path = folder / filename
            task = self.download_image(url, save_path)
            tasks.append((task, save_path))

        results = await asyncio.gather(*[task for task, _ in tasks], return_exceptions=True)

        successful_paths = []
        for (_, path), result in zip(tasks, results):
            if result is True and path.exists():
                successful_paths.append(path)

        logger.info(f"Downloaded {len(successful_paths)}/{len(urls)} images")
        return successful_paths

    async def scrape_item_page_images(self, item_url: str) -> List[str]:
        """
        Scrape an item page and extract all image URLs from it.

        Args:
            item_url: URL of the item page to scrape

        Returns:
            List of all image URLs found on the page
        """
        if not self.session:
            logger.error("Session not initialized. Use 'async with' context.")
            return []

        if not BS4_AVAILABLE:
            logger.warning("BeautifulSoup not available, cannot scrape web pages")
            return []

        logger.info(f"Starting web scraping for: {item_url}")

        max_retries = 2
        for attempt in range(max_retries):
            try:
                async with self.session.get(item_url) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to fetch item page {item_url}: {response.status}")
                        return []

                    html_content = await response.text()
                    soup = BeautifulSoup(html_content, 'html.parser')

                    # Extract all image URLs from the page
                    image_urls = []
                    img_tags = soup.find_all('img')

                    for img_tag in img_tags:
                        img_src = img_tag.get('src')
                        if not img_src:
                            continue

                        # Handle relative URLs
                        img_url = urljoin(item_url, img_src)

                        # Filter out non-HTTP URLs and data URLs
                        if not img_url.startswith(('http://', 'https://')):
                            continue

                        # Better filtering for product images
                        if self._is_product_image_v2(img_url, img_tag):
                            image_urls.append(img_url)

                    # Also look for images in CSS background-image properties
                    css_images = self._extract_css_background_images(soup, item_url)
                    image_urls.extend(css_images)

                    # Remove duplicates while preserving order (better deduplication)
                    unique_urls = []
                    seen = set()
                    for url in image_urls:
                        if url not in seen:
                            seen.add(url)
                            unique_urls.append(url)

                    # Additional deduplication: remove images that are essentially the same
                    # (same base URL with different parameters)
                    deduplicated_urls = []
                    seen_bases = set()

                    for url in unique_urls:
                        # Extract base URL without parameters for comparison
                        base_url = url.split('?')[0] if '?' in url else url
                        # Remove size indicators from path
                        base_url = base_url.replace('/f800/', '/').replace('/f600/', '/').replace('/f400/', '/')

                        if base_url not in seen_bases:
                            seen_bases.add(base_url)
                            deduplicated_urls.append(url)

                    logger.info(f"Scraped {len(unique_urls)} total, {len(deduplicated_urls)} unique images from {item_url}")
                    return deduplicated_urls[:10]  # Limit to 10 images as per requirements

            except Exception as e:
                if self._is_ssl_error(e) and attempt < max_retries - 1:
                    logger.warning(f"SSL error for {item_url}, retrying without SSL: {e}")
                    if self._handle_ssl_error():
                        # Need to recreate session with new SSL settings
                        await self.session.close()
                        connector = self._create_connector()
                        timeout = aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT)
                        self.session = aiohttp.ClientSession(
                            connector=connector,
                            timeout=timeout,
                            headers={
                                'User-Agent': 'Mozilla/5.0 (compatible; TelegramBot/1.0)',
                                'Accept': 'image/*'
                            }
                        )
                        continue

                logger.error(f"Error scraping item page {item_url}: {e}")
                return []

        return []

    def _is_product_image(self, img_url: str, img_tag) -> bool:
        """
        Determine if an image URL is likely a product image.

        Args:
            img_url: Image URL to check
            img_tag: BeautifulSoup img tag object

        Returns:
            True if likely a product image, False otherwise
        """
        url_lower = img_url.lower()

        # Skip obvious non-product images
        skip_patterns = [
            'icon', 'logo', 'banner', 'avatar', 'profile',
            'button', 'arrow', 'loading', 'spinner',
            'pixel', 'spacer', 'transparent'
        ]

        if any(pattern in url_lower for pattern in skip_patterns):
            return False

        # Check image dimensions if available
        width = img_tag.get('width')
        height = img_tag.get('height')

        if width and height:
            try:
                width = int(width)
                height = int(height)
                # Skip very small images (likely icons)
                if width < 100 or height < 100:
                    return False
                # Skip extremely large images (likely banners)
                if width > 2000 or height > 2000:
                    return False
            except (ValueError, TypeError):
                pass

        # Check CSS classes or alt text for product indicators
        classes = img_tag.get('class', [])
        alt_text = img_tag.get('alt', '').lower()

        product_indicators = ['product', 'item', 'photo', 'image', 'pic']
        if any(indicator in ' '.join(classes).lower() for indicator in product_indicators):
            return True
        if any(indicator in alt_text for indicator in product_indicators):
            return True

        # Check for common e-commerce image patterns
        if any(pattern in url_lower for pattern in ['photo', 'image', 'img', 'picture']):
            return True

        # Default to True for images that pass basic filters
        return True

    def _is_product_image_v2(self, img_url: str, img_tag) -> bool:
        """
        Improved version: Better filtering for product images vs UI elements.

        Args:
            img_url: Image URL to check
            img_tag: BeautifulSoup img tag object

        Returns:
            True if likely a product image, False otherwise
        """
        url_lower = img_url.lower()
        alt_text = img_tag.get('alt', '').lower()

        # Skip obvious UI elements and icons
        skip_patterns = [
            'icon', 'logo', 'banner', 'avatar', 'button',
            'social', 'facebook', 'instagram', 'linkedin',
            'twitter', 'youtube', 'app store', 'google play',
            'svg', 'static/media', 'marketplace-web-assets'
        ]

        if any(skip in url_lower for skip in skip_patterns):
            return False

        # Keep images that are likely product photos
        is_product_image = False

        # Check if it's from Vinted's main image CDN
        if 'images1.vinted.net' in url_lower or 'images.vinted.net' in url_lower:
            is_product_image = True

        # Check alt text for product indicators (brand names, sizes, etc.)
        product_keywords = ['nike', 'adidas', 'zara', 'h&m', 'sweater', 'shirt', 'jeans', 'dress', 'shoes', 'sneakers']
        if any(word in alt_text for word in product_keywords):
            is_product_image = True

        # Check if alt text contains numbers (likely product image numbers)
        import re
        if re.search(r'\d+', alt_text):
            is_product_image = True

        # Additional check: avoid very small images or icons
        width = img_tag.get('width')
        height = img_tag.get('height')
        if width and height:
            try:
                width = int(width)
                height = int(height)
                if width < 100 or height < 100:
                    is_product_image = False
            except (ValueError, TypeError):
                pass

        return is_product_image

    def _extract_css_background_images(self, soup, base_url: str) -> List[str]:
        """
        Extract background images from CSS styles.

        Args:
            soup: BeautifulSoup object
            base_url: Base URL for resolving relative URLs

        Returns:
            List of background image URLs
        """
        background_images = []

        # Look for style attributes
        elements_with_style = soup.find_all(attrs={'style': True})
        for element in elements_with_style:
            style = element.get('style', '')
            if 'background-image' in style:
                # Simple regex to extract URL from background-image
                import re
                url_match = re.search(r'background-image:\s*url\(["\']?([^"\']+)["\']?\)', style)
                if url_match:
                    img_url = urljoin(base_url, url_match.group(1))
                    if img_url.startswith(('http://', 'https://')):
                        background_images.append(img_url)

        return background_images

# Helper functions for image extraction
def extract_images_from_item(item: Dict[str, Any]) -> List[str]:
    """Extract image URLs from a Vinted item."""
    images = []

    # Extract from photos array
    photos = item.get('photos', [])
    for photo in photos:
        if isinstance(photo, dict):
            # Try different possible URL keys
            for key in ['full_size_url', 'url', 'image_url']:
                if key in photo and photo[key]:
                    images.append(photo[key])
                    break
        elif isinstance(photo, str):
            images.append(photo)

    # Extract from single photo field
    if 'photo' in item:
        photo = item['photo']
        if isinstance(photo, dict):
            for key in ['full_size_url', 'url', 'image_url']:
                if key in photo and photo[key]:
                    images.append(photo[key])
                    break
        elif isinstance(photo, str):
            images.append(photo)

    # Remove duplicates
    unique_images = []
    seen = set()
    for img in images:
        if img not in seen:
            seen.add(img)
            unique_images.append(img)

    return unique_images

def filter_valid_images(image_urls: List[str]) -> List[str]:
    """Filter valid image URLs."""
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    valid_images = []

    for url in image_urls:
        if not url or not isinstance(url, str):
            continue

        url_lower = url.lower()
        is_valid = any(url_lower.endswith(ext) for ext in valid_extensions)
        is_valid = is_valid or any(pattern in url_lower for pattern in ['images', 'photos', 'img'])

        if is_valid and url.startswith(('http://', 'https://')):
            valid_images.append(url)

    return valid_images

# Convenience functions
async def download_item_images(item: Dict[str, Any], folder: Path) -> List[Path]:
    """Download all images for a Vinted item."""
    from .image_extraction_service import get_image_extraction_service

    # Get image URLs from the item
    image_urls = extract_images_from_item(item)
    valid_urls = filter_valid_images(image_urls)
    
    if not valid_urls:
        return []
        
    async with ImageDownloader() as downloader:
        return await downloader.download_batch(valid_urls, folder)

async def download_single_image(url: str, save_path: Path) -> bool:
    """Download one image file."""
    async with ImageDownloader() as downloader:
        return await downloader.download_image(url, save_path)

async def scrape_item_images(item_url: str) -> List[str]:
    """
    Scrape all images from an item page.

    Args:
        item_url: URL of the item page to scrape

    Returns:
        List of all image URLs found on the page
    """
    try:
        async with ImageDownloader() as downloader:
            logger.info(f"Scraping images from: {item_url}")
            result = await downloader.scrape_item_page_images(item_url)
            logger.info(f"Found {len(result)} images via scraping")
            return result
    except Exception as e:
        logger.error(f"Error in scrape_item_images: {e}")
        return []

# Utility functions for image extraction from Vinted items
def extract_images_from_item_api(item: Dict[str, Any]) -> List[str]:
    """
    Extract image URLs from Vinted item using API data only (fallback method).

    Args:
        item: Vinted item dictionary

    Returns:
        List of image URLs
    """
    images = []

    # Extract from photos array
    photos = item.get('photos', [])
    for photo in photos:
        if isinstance(photo, dict):
            # Try different possible URL keys
            for key in ['full_size_url', 'url', 'image_url']:
                if key in photo and photo[key]:
                    images.append(photo[key])
                    break
        elif isinstance(photo, str):
            images.append(photo)

    # Extract from single photo field
    if 'photo' in item:
        photo = item['photo']
        if isinstance(photo, dict):
            for key in ['full_size_url', 'url', 'image_url']:
                if key in photo and photo[key]:
                    images.append(photo[key])
                    break
        elif isinstance(photo, str):
            images.append(photo)

    # Remove duplicates
    unique_images = []
    seen = set()
    for img in images:
        if img not in seen:
            seen.add(img)
            unique_images.append(img)

    return unique_images

def filter_valid_image_urls(image_urls: List[str]) -> List[str]:
    """
    Filter image URLs to keep only valid ones.

    Args:
        image_urls: List of image URLs to filter

    Returns:
        List of valid image URLs
    """
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    valid_images = []

    for url in image_urls:
        if not url or not isinstance(url, str):
            continue

        url_lower = url.lower()
        is_valid = any(url_lower.endswith(ext) for ext in valid_extensions)
        is_valid = is_valid or any(pattern in url_lower for pattern in ['images', 'photos', 'img'])

        if is_valid and url.startswith(('http://', 'https://')):
            valid_images.append(url)

    return valid_images

class TelegramImageService:
    """Service for handling images in Telegram bot output."""

    def __init__(self):
        """Initialize the Telegram image service."""
        self.cache_dir = CACHE_DIR / "telegram"
        self.cache_dir.mkdir(exist_ok=True)

    async def prepare_images_for_telegram(self, image_urls: List[str]) -> List[str]:
        """Download and prepare images for Telegram bot output.

        Returns local file paths that can be uploaded to Telegram.
        """
        if not image_urls:
            return []

        logger.info(f"Preparing {len(image_urls)} images for Telegram")

        downloaded_paths = []
        async with ImageDownloader() as downloader:
            for i, url in enumerate(image_urls[:10]):  # Limit to 10 images max
                try:
                    filename = f"telegram_image_{i:03d}.jpg"
                    save_path = self.cache_dir / filename

                    success = await downloader.download_image(url, save_path, use_cache=True)
                    if success and save_path.exists():
                        downloaded_paths.append(str(save_path))
                        logger.debug(f"Prepared image {i+1}: {save_path.name}")
                    else:
                        logger.warning(f"Failed to prepare image {i+1}: {url}")

                except Exception as e:
                    logger.error(f"Error preparing image {i+1}: {e}")
                    continue

        logger.info(f"Successfully prepared {len(downloaded_paths)}/{len(image_urls)} images for Telegram")
        return downloaded_paths

    async def cleanup_old_cache(self, max_age_hours: int = 24):
        """Clean up old cached images."""
        try:
            import time
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600

            removed_count = 0
            for cache_file in self.cache_dir.glob("*.jpg"):
                if current_time - cache_file.stat().st_mtime > max_age_seconds:
                    cache_file.unlink()
                    removed_count += 1

            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} old cached images")

        except Exception as e:
            logger.warning(f"Cache cleanup failed: {e}")

# Global instance
_telegram_image_service = None

def get_telegram_image_service() -> TelegramImageService:
    """Get global Telegram image service instance."""
    global _telegram_image_service
    if _telegram_image_service is None:
        _telegram_image_service = TelegramImageService()
    return _telegram_image_service

