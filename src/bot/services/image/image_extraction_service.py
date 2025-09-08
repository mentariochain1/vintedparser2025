"""
Image Extraction Service for Vinted Telegram Bot.

Provides local image processing capabilities including OCR text extraction,
object detection, and metadata analysis. Designed for production use
with security, performance, and async compatibility in mind.
"""

import asyncio
import tempfile
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import hashlib
import time

import aiofiles

# Optional imports with fallbacks
try:
    from PIL import Image, ImageFilter, ImageEnhance
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None
    ImageFilter = None
    ImageEnhance = None

try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    cv2 = None
    np = None

from .config import (
    get_security_config,
    get_tesseract_config,
    get_cache_config,
    MAX_CONCURRENT_EXTRACTIONS,
    PROCESSING_TIMEOUT
)

logger = logging.getLogger(__name__)

# Constants from config module
CACHE_EXPIRY_HOURS = 24

class ExtractionType(Enum):
    """Types of image extraction supported."""
    OCR_TEXT = "ocr_text"
    OBJECT_DETECTION = "object_detection"
    METADATA = "metadata"
    ALL = "all"

class ProcessingQuality(Enum):
    """Quality levels for image processing."""
    FAST = "fast"
    BALANCED = "balanced"
    HIGH = "high"

@dataclass
class ImageMetadata:
    """Metadata extracted from image."""
    format: str
    width: int
    height: int
    color_mode: str
    file_size: int
    dpi: Optional[Tuple[int, int]]
    has_alpha: bool
    dominant_colors: List[Tuple[int, int, int]]

@dataclass
class OCRResult:
    """OCR extraction result."""
    text: str
    confidence: float
    language: str
    bounding_boxes: List[Dict[str, Any]]

@dataclass
class ObjectDetection:
    """Object detection result."""
    objects: List[Dict[str, Any]]
    confidence_threshold: float
    model_used: str

@dataclass
class ExtractionResult:
    """Complete extraction result."""
    success: bool
    image_hash: str
    metadata: Optional[ImageMetadata] = None
    ocr_result: Optional[OCRResult] = None
    object_detection: Optional[ObjectDetection] = None
    processing_time: float = 0.0
    error_message: Optional[str] = None

class ImageExtractionService:
    """
    Production-ready image extraction service with security and performance optimizations.

    Features:
    - OCR text extraction using Tesseract
    - Object detection capabilities
    - Metadata extraction
    - Security validations
    - Performance optimizations
    - Async compatibility
    - Caching support
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        tesseract_config: Optional[Dict[str, Any]] = None,
        security_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the image extraction service.

        Args:
            cache_dir: Directory for caching processed images (overrides config)
            tesseract_config: Configuration for Tesseract OCR (overrides config)
            security_config: Security-related configurations (overrides config)
        """
        # Use provided configs or load from config module
        cache_config = get_cache_config()
        self.cache_dir = cache_dir or cache_config['cache_dir']
        self.cache_dir.mkdir(exist_ok=True)

        # Tesseract configuration
        self.tesseract_config = tesseract_config or get_tesseract_config()

        # Security configuration
        self.security_config = security_config or get_security_config()

        # Initialize cache
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cleanup_cache()

    def _cleanup_cache(self) -> None:
        """Clean up expired cache entries."""
        try:
            current_time = time.time()
            expiry_time = CACHE_EXPIRY_HOURS * 3600

            for cache_file in self.cache_dir.glob("*.cache"):
                if current_time - cache_file.stat().st_mtime > expiry_time:
                    cache_file.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Cache cleanup failed: {e}")

    def _calculate_image_hash(self, image_path: Path) -> str:
        """Calculate SHA256 hash of image file."""
        hash_sha256 = hashlib.sha256()
        with open(image_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def _validate_image_file(self, file_path: Path) -> bool:
        """
        Validate image file for security and format compliance.

        Args:
            file_path: Path to the image file

        Returns:
            True if valid, False otherwise
        """
        try:
            # Check file extension
            if file_path.suffix.lower() not in self.security_config['allowed_formats']:
                logger.warning(f"Unsupported file format: {file_path.suffix}")
                return False

            # Check file size
            file_size = file_path.stat().st_size
            if file_size > self.security_config['max_file_size']:
                logger.warning(f"File too large: {file_size} bytes")
                return False

            # Validate image format and dimensions (if PIL available)
            if PIL_AVAILABLE:
                try:
                    with Image.open(file_path) as img:
                        width, height = img.size

                        if width > self.security_config['max_dimension'] or height > self.security_config['max_dimension']:
                            logger.warning(f"Image dimensions too large: {width}x{height}")
                            return False

                        if width < self.security_config['min_dimension'] or height < self.security_config['min_dimension']:
                            logger.warning(f"Image dimensions too small: {width}x{height}")
                            return False
                except Exception as e:
                    logger.warning(f"PIL validation failed: {e}")
                    # Fallback: just check file exists and has content
                    if file_size == 0:
                        return False
            else:
                logger.info("PIL not available, skipping detailed image validation")
                # Basic validation without PIL
                if file_size == 0:
                    return False

            return True

        except Exception as e:
            logger.error(f"Image validation failed: {e}")
            return False

    def _preprocess_image_for_ocr(self, image, quality: ProcessingQuality):
        """
        Preprocess image for optimal OCR results.

        Args:
            image: PIL Image object
            quality: Processing quality level

        Returns:
            Preprocessed PIL Image
        """
        if not PIL_AVAILABLE:
            logger.warning("PIL not available, cannot preprocess image for OCR")
            return image

        # Convert to grayscale
        if image.mode != 'L':
            image = image.convert('L')

        # Apply quality-specific preprocessing
        if quality == ProcessingQuality.FAST:
            # Basic preprocessing
            image = image.filter(ImageFilter.SHARPEN)
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0)

        elif quality == ProcessingQuality.BALANCED:
            # Medium preprocessing
            image = image.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.5)
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(2.0)

        elif quality == ProcessingQuality.HIGH:
            # Advanced preprocessing
            # Noise reduction
            image = image.filter(ImageFilter.MedianFilter(size=3))
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(3.0)
            # Sharpen
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(2.5)
            # Slight blur to reduce noise
            image = image.filter(ImageFilter.GaussianBlur(radius=0.5))

        return image

    async def _extract_metadata_async(self, image_path: Path) -> ImageMetadata:
        """
        Extract comprehensive metadata from image.

        Args:
            image_path: Path to image file

        Returns:
            ImageMetadata object
        """
        def _extract_metadata_sync() -> ImageMetadata:
            file_size = image_path.stat().st_size

            if PIL_AVAILABLE:
                try:
                    with Image.open(image_path) as img:
                        # Basic metadata
                        width, height = img.size
                        format_name = img.format or "Unknown"
                        color_mode = img.mode

                        # DPI information
                        dpi = img.info.get('dpi')
                        if isinstance(dpi, (tuple, list)) and len(dpi) >= 2:
                            dpi = (int(dpi[0]), int(dpi[1]))
                        else:
                            dpi = None

                        # Alpha channel check
                        has_alpha = img.mode in ('RGBA', 'LA', 'P')

                        # Dominant colors (simplified)
                        dominant_colors = self._extract_dominant_colors(img)

                        return ImageMetadata(
                            format=format_name,
                            width=width,
                            height=height,
                            color_mode=color_mode,
                            file_size=file_size,
                            dpi=dpi,
                            has_alpha=has_alpha,
                            dominant_colors=dominant_colors
                        )
                except Exception as e:
                    logger.warning(f"PIL metadata extraction failed: {e}")

            # Fallback metadata without PIL
            return ImageMetadata(
                format="Unknown",
                width=0,
                height=0,
                color_mode="Unknown",
                file_size=file_size,
                dpi=None,
                has_alpha=False,
                dominant_colors=[]
            )

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _extract_metadata_sync)

    def _extract_dominant_colors(self, image, num_colors: int = 5) -> List[Tuple[int, int, int]]:
        """
        Extract dominant colors from image.

        Args:
            image: PIL Image object
            num_colors: Number of dominant colors to extract

        Returns:
            List of RGB tuples
        """
        if not PIL_AVAILABLE:
            return [(128, 128, 128)]  # Default gray

        try:
            # Resize for faster processing
            small_image = image.resize((150, 150))
            # Convert to RGB if necessary
            if small_image.mode != 'RGB':
                small_image = small_image.convert('RGB')

            # Get colors
            colors = small_image.getcolors(150 * 150)
            if not colors:
                return [(128, 128, 128)]  # Default gray

            # Sort by frequency and return top colors
            sorted_colors = sorted(colors, key=lambda x: x[0], reverse=True)
            return [color for count, color in sorted_colors[:num_colors]]

        except Exception as e:
            logger.warning(f"Failed to extract dominant colors: {e}")
            return [(128, 128, 128)]

    async def _perform_ocr_async(
        self,
        image_path: Path,
        quality: ProcessingQuality,
        language: Optional[str] = None
    ) -> OCRResult:
        """
        Perform OCR on image.

        Args:
            image_path: Path to image file
            quality: Processing quality level
            language: OCR language (optional)

        Returns:
            OCRResult object
        """
        try:
            import pytesseract
            from pytesseract import Output

            def _ocr_sync() -> OCRResult:
                if not PIL_AVAILABLE:
                    logger.warning("PIL not available, OCR cannot be performed")
                    return OCRResult(text="", confidence=0.0, language=language or "unknown", bounding_boxes=[])

                with Image.open(image_path) as img:
                    # Preprocess image
                    processed_img = self._preprocess_image_for_ocr(img, quality)

                    # Set language
                    lang = language or self.tesseract_config['lang']

                    # Perform OCR with detailed data
                    data = pytesseract.image_to_data(
                        processed_img,
                        lang=lang,
                        config=self.tesseract_config['config'],
                        output_type=Output.DICT
                    )

                    # Extract text and calculate confidence
                    text_parts = []
                    confidences = []
                    bounding_boxes = []

                    n_boxes = len(data['text'])
                    for i in range(n_boxes):
                        text = data['text'][i].strip()
                        if text:  # Only non-empty text
                            confidence = int(data['conf'][i])
                            if confidence > 0:  # Filter out low confidence
                                text_parts.append(text)
                                confidences.append(confidence)

                                bounding_boxes.append({
                                    'text': text,
                                    'confidence': confidence,
                                    'left': data['left'][i],
                                    'top': data['top'][i],
                                    'width': data['width'][i],
                                    'height': data['height'][i]
                                })

                    # Combine text
                    full_text = ' '.join(text_parts)

                    # Calculate average confidence
                    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

                    return OCRResult(
                        text=full_text,
                        confidence=avg_confidence,
                        language=lang,
                        bounding_boxes=bounding_boxes
                    )

            # Run in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _ocr_sync)

        except ImportError:
            logger.warning("pytesseract not available, OCR will not work")
            return OCRResult(text="", confidence=0.0, language=language or "unknown", bounding_boxes=[])
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return OCRResult(text="", confidence=0.0, language=language or "unknown", bounding_boxes=[])

    async def _perform_object_detection_async(self, image_path: Path) -> ObjectDetection:
        """
        Perform object detection on image.

        Args:
            image_path: Path to image file

        Returns:
            ObjectDetection object
        """
        if not OPENCV_AVAILABLE:
            logger.info("OpenCV not available, object detection disabled")
            return ObjectDetection(objects=[], confidence_threshold=0.5, model_used="unavailable")

        try:
            # For now, using OpenCV's basic object detection
            # In production, you might want to use more sophisticated models

            def _detect_sync() -> ObjectDetection:
                # Read image with OpenCV
                img = cv2.imread(str(image_path))
                if img is None:
                    return ObjectDetection(objects=[], confidence_threshold=0.5, model_used="opencv_basic")

                # Convert to grayscale
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

                # Simple edge detection as basic object detection
                edges = cv2.Canny(gray, 100, 200)

                # Find contours (potential objects)
                contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                objects = []
                for i, contour in enumerate(contours):
                    # Filter small contours
                    area = cv2.contourArea(contour)
                    if area < 100:  # Minimum area threshold
                        continue

                    # Get bounding box
                    x, y, w, h = cv2.boundingRect(contour)

                    objects.append({
                        'id': i,
                        'label': 'object',
                        'confidence': 0.5,  # Placeholder confidence
                        'bbox': [x, y, x + w, y + h],
                        'area': area
                    })

                return ObjectDetection(
                    objects=objects,
                    confidence_threshold=0.5,
                    model_used="opencv_contour_detection"
                )

            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _detect_sync)

        except Exception as e:
            logger.error(f"Object detection failed: {e}")
            return ObjectDetection(objects=[], confidence_threshold=0.5, model_used="failed")

    async def extract_from_file(
        self,
        file_path: Union[str, Path],
        extraction_types: List[ExtractionType] = None,
        quality: ProcessingQuality = ProcessingQuality.BALANCED,
        language: Optional[str] = None,
        use_cache: bool = True
    ) -> ExtractionResult:
        """
        Extract information from image file.

        Args:
            file_path: Path to image file
            extraction_types: Types of extraction to perform
            quality: Processing quality level
            language: OCR language
            use_cache: Whether to use caching

        Returns:
            ExtractionResult object
        """
        start_time = time.time()
        file_path = Path(file_path)

        # Set default extraction types
        if extraction_types is None:
            extraction_types = [ExtractionType.ALL]

        if ExtractionType.ALL in extraction_types:
            extraction_types = [ExtractionType.METADATA, ExtractionType.OCR_TEXT, ExtractionType.OBJECT_DETECTION]

        try:
            # Validate file
            if not self._validate_image_file(file_path):
                return ExtractionResult(
                    success=False,
                    image_hash="",
                    error_message="Invalid image file",
                    processing_time=time.time() - start_time
                )

            # Calculate image hash
            image_hash = self._calculate_image_hash(file_path)

            # Check cache
            if use_cache:
                cache_key = f"{image_hash}_{quality.value}_{language or 'auto'}"
                if cache_key in self._cache:
                    cached_result = self._cache[cache_key]
                    if time.time() - cached_result['timestamp'] < CACHE_EXPIRY_HOURS * 3600:
                        logger.info(f"Cache hit for {file_path.name}")
                        return cached_result['result']

            # Perform extractions
            result = ExtractionResult(success=True, image_hash=image_hash)

            # Metadata extraction (always performed if requested)
            if ExtractionType.METADATA in extraction_types:
                result.metadata = await self._extract_metadata_async(file_path)

            # OCR extraction
            if ExtractionType.OCR_TEXT in extraction_types:
                result.ocr_result = await self._perform_ocr_async(file_path, quality, language)

            # Object detection
            if ExtractionType.OBJECT_DETECTION in extraction_types:
                result.object_detection = await self._perform_object_detection_async(file_path)

            result.processing_time = time.time() - start_time

            # Cache result
            if use_cache:
                cache_key = f"{image_hash}_{quality.value}_{language or 'auto'}"
                self._cache[cache_key] = {
                    'result': result,
                    'timestamp': time.time()
                }

            logger.info(f"Extraction completed for {file_path.name} in {result.processing_time:.2f}s")
            return result

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return ExtractionResult(
                success=False,
                image_hash="",
                error_message=str(e),
                processing_time=time.time() - start_time
            )

    async def extract_from_bytes(
        self,
        image_bytes: bytes,
        filename: str = "temp_image.jpg",
        extraction_types: List[ExtractionType] = None,
        quality: ProcessingQuality = ProcessingQuality.BALANCED,
        language: Optional[str] = None
    ) -> ExtractionResult:
        """
        Extract information from image bytes.

        Args:
            image_bytes: Raw image bytes
            filename: Temporary filename to use
            extraction_types: Types of extraction to perform
            quality: Processing quality level
            language: OCR language

        Returns:
            ExtractionResult object
        """
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix, delete=False) as temp_file:
            temp_file.write(image_bytes)
            temp_path = Path(temp_file.name)

        try:
            # Extract from temporary file
            result = await self.extract_from_file(
                temp_path,
                extraction_types,
                quality,
                language,
                use_cache=False  # Don't cache temporary files
            )

        finally:
            # Clean up temporary file
            temp_path.unlink(missing_ok=True)

        return result

    async def batch_extract(
        self,
        file_paths: List[Union[str, Path]],
        extraction_types: List[ExtractionType] = None,
        quality: ProcessingQuality = ProcessingQuality.BALANCED,
        language: Optional[str] = None,
        max_concurrent: Optional[int] = None
    ) -> List[ExtractionResult]:
        """
        Extract information from multiple images concurrently.

        Args:
            file_paths: List of image file paths
            extraction_types: Types of extraction to perform
            quality: Processing quality level
            language: OCR language
            max_concurrent: Maximum concurrent extractions (uses config default if None)

        Returns:
            List of ExtractionResult objects
        """
        async def extract_single(file_path: Union[str, Path]) -> ExtractionResult:
            return await self.extract_from_file(file_path, extraction_types, quality, language)

        # Create semaphore for concurrency control
        concurrent_limit = max_concurrent or MAX_CONCURRENT_EXTRACTIONS
        semaphore = asyncio.Semaphore(concurrent_limit)

        async def extract_with_semaphore(file_path: Union[str, Path]) -> ExtractionResult:
            async with semaphore:
                return await extract_single(file_path)

        # Process all files concurrently
        tasks = [extract_with_semaphore(Path(fp)) for fp in file_paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch extraction failed for {file_paths[i]}: {result}")
                final_results.append(ExtractionResult(
                    success=False,
                    image_hash="",
                    error_message=str(result)
                ))
            else:
                final_results.append(result)

        return final_results

# Convenience functions for easy integration
async def extract_image_text(
    file_path: Union[str, Path],
    quality: ProcessingQuality = ProcessingQuality.BALANCED,
    language: Optional[str] = None
) -> str:
    """
    Extract text from image file.

    Args:
        file_path: Path to image file
        quality: Processing quality level
        language: OCR language

    Returns:
        Extracted text
    """
    service = ImageExtractionService()
    result = await service.extract_from_file(
        file_path,
        [ExtractionType.OCR_TEXT],
        quality,
        language
    )

    if result.success and result.ocr_result:
        return result.ocr_result.text
    return ""

async def extract_image_metadata(file_path: Union[str, Path]) -> Optional[ImageMetadata]:
    """
    Extract metadata from image file.

    Args:
        file_path: Path to image file

    Returns:
        ImageMetadata object or None
    """
    service = ImageExtractionService()
    result = await service.extract_from_file(file_path, [ExtractionType.METADATA])

    if result.success:
        return result.metadata
    return None

# Global instance for convenience
_extraction_service = None

def get_image_extraction_service() -> ImageExtractionService:
    """Get global image extraction service instance."""
    global _extraction_service
    if _extraction_service is None:
        _extraction_service = ImageExtractionService()
    return _extraction_service
