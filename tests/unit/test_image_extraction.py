"""
Unit tests for Image Extraction Service.

Tests cover security validation, OCR functionality, metadata extraction,
and performance optimizations.
"""

import pytest
import asyncio
from pathlib import Path
from PIL import Image, ImageDraw
import tempfile

from src.bot.services.image.image_extraction_service import (
    ImageExtractionService,
    ExtractionType,
    ProcessingQuality,
    ExtractionResult,
    ImageMetadata,
    OCRResult,
    ObjectDetection
)


class TestImageExtractionService:
    """Test cases for ImageExtractionService."""

    @pytest.fixture
    def service(self):
        """Create a fresh service instance for each test."""
        return ImageExtractionService()

    @pytest.fixture
    def sample_image_path(self):
        """Create a temporary sample image for testing."""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            # Create a simple test image with text
            img = Image.new('RGB', (200, 100), color='white')
            draw = ImageDraw.Draw(img)
            draw.text((10, 30), "TEST IMAGE", fill='black')
            img.save(tmp.name)
            tmp_path = Path(tmp.name)

        yield tmp_path
        # Cleanup
        tmp_path.unlink(missing_ok=True)

    @pytest.fixture
    def large_image_path(self):
        """Create a large image that should be rejected."""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            # Create image larger than MAX_IMAGE_DIMENSION
            img = Image.new('RGB', (5000, 5000), color='white')
            img.save(tmp.name)
            tmp_path = Path(tmp.name)

        yield tmp_path
        # Cleanup
        tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_validate_image_file_valid(self, service, sample_image_path):
        """Test validation of valid image file."""
        assert service._validate_image_file(sample_image_path)

    @pytest.mark.asyncio
    async def test_validate_image_file_large_dimension(self, service, large_image_path):
        """Test rejection of oversized image."""
        assert not service._validate_image_file(large_image_path)

    @pytest.mark.asyncio
    async def test_validate_image_file_invalid_format(self, service):
        """Test rejection of invalid file format."""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
            tmp.write(b"This is not an image")
            tmp_path = Path(tmp.name)

        try:
            assert not service._validate_image_file(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_extract_metadata(self, service, sample_image_path):
        """Test metadata extraction."""
        result = await service.extract_from_file(
            sample_image_path,
            [ExtractionType.METADATA]
        )

        assert result.success
        assert result.metadata is not None
        assert isinstance(result.metadata, ImageMetadata)
        assert result.metadata.width == 200
        assert result.metadata.height == 100
        assert result.metadata.format == "PNG"

    @pytest.mark.asyncio
    async def test_extract_from_file_invalid_path(self, service):
        """Test handling of invalid file path."""
        result = await service.extract_from_file(
            "/nonexistent/path/image.jpg",
            [ExtractionType.METADATA]
        )

        assert not result.success
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_extract_from_bytes(self, service):
        """Test extraction from image bytes."""
        # Create test image in memory
        img = Image.new('RGB', (100, 100), color='red')
        from io import BytesIO
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        image_bytes = buffer.getvalue()

        result = await service.extract_from_bytes(
            image_bytes,
            "test.png",
            [ExtractionType.METADATA]
        )

        assert result.success
        assert result.metadata is not None
        assert result.metadata.width == 100
        assert result.metadata.height == 100

    @pytest.mark.asyncio
    async def test_batch_extract(self, service, sample_image_path):
        """Test batch extraction functionality."""
        # Create multiple copies of the sample image
        image_paths = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                # Copy the sample image
                import shutil
                shutil.copy2(sample_image_path, tmp.name)
                image_paths.append(Path(tmp.name))

        try:
            results = await service.batch_extract(
                image_paths,
                [ExtractionType.METADATA],
                max_concurrent=2
            )

            assert len(results) == 3
            for result in results:
                assert result.success
                assert result.metadata is not None

        finally:
            # Cleanup
            for path in image_paths:
                path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_cache_functionality(self, service, sample_image_path):
        """Test caching functionality."""
        # First extraction
        result1 = await service.extract_from_file(
            sample_image_path,
            [ExtractionType.METADATA]
        )

        # Second extraction (should use cache)
        result2 = await service.extract_from_file(
            sample_image_path,
            [ExtractionType.METADATA]
        )

        assert result1.success
        assert result2.success
        assert result1.image_hash == result2.image_hash
        assert result1.metadata == result2.metadata

    @pytest.mark.asyncio
    async def test_processing_quality_levels(self, service, sample_image_path):
        """Test different processing quality levels."""
        for quality in ProcessingQuality:
            result = await service.extract_from_file(
                sample_image_path,
                [ExtractionType.METADATA],
                quality=quality
            )
            assert result.success

    @pytest.mark.asyncio
    async def test_ocr_fallback_on_missing_tesseract(self, service, sample_image_path):
        """Test OCR graceful fallback when Tesseract is not available."""
        # Mock pytesseract import failure
        import sys
        original_import = __builtins__.__import__

        def mock_import(name, *args, **kwargs):
            if name == 'pytesseract':
                raise ImportError("No module named 'pytesseract'")
            return original_import(name, *args, **kwargs)

        __builtins__.__import__ = mock_import

        try:
            result = await service.extract_from_file(
                sample_image_path,
                [ExtractionType.OCR_TEXT]
            )

            # Should fail gracefully
            assert not result.success or (result.ocr_result and result.ocr_result.confidence == 0.0)

        finally:
            __builtins__.__import__ = original_import

    @pytest.mark.asyncio
    async def test_object_detection_basic(self, service, sample_image_path):
        """Test basic object detection functionality."""
        result = await service.extract_from_file(
            sample_image_path,
            [ExtractionType.OBJECT_DETECTION]
        )

        assert result.success
        assert result.object_detection is not None
        assert isinstance(result.object_detection, ObjectDetection)

    def test_dominant_colors_extraction(self, service):
        """Test dominant colors extraction."""
        # Create test image with known colors
        img = Image.new('RGB', (100, 100), color='red')

        colors = service._extract_dominant_colors(img)
        assert len(colors) > 0
        assert all(isinstance(color, tuple) and len(color) == 3 for color in colors)


class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.mark.asyncio
    async def test_extract_image_text(self, sample_image_path):
        """Test text extraction convenience function."""
        from src.bot.services.image import extract_image_text

        text = await extract_image_text(sample_image_path)
        assert isinstance(text, str)

    @pytest.mark.asyncio
    async def test_extract_image_metadata(self, sample_image_path):
        """Test metadata extraction convenience function."""
        from src.bot.services.image import extract_image_metadata

        metadata = await extract_image_metadata(sample_image_path)
        assert metadata is None or isinstance(metadata, ImageMetadata)


class TestSecurity:
    """Security-related test cases."""

    def test_file_size_limit(self, service):
        """Test file size validation."""
        # Create a file larger than the limit
        config = service.security_config.copy()
        config['max_file_size'] = 100  # Very small limit

        service_with_limit = ImageExtractionService(security_config=config)

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            # Write more data than the limit
            tmp.write(b'x' * 200)
            tmp_path = Path(tmp.name)

        try:
            assert not service_with_limit._validate_image_file(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_dimension_limits(self, service):
        """Test dimension validation."""
        config = service.security_config.copy()
        config['max_dimension'] = 50  # Small limit

        service_with_limit = ImageExtractionService(security_config=config)

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            # Create image larger than limit
            img = Image.new('RGB', (100, 100), color='white')
            img.save(tmp.name)
            tmp_path = Path(tmp.name)

        try:
            assert not service_with_limit._validate_image_file(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)


# Performance tests
@pytest.mark.performance
class TestPerformance:
    """Performance-related test cases."""

    @pytest.mark.asyncio
    async def test_concurrent_processing(self, service, sample_image_path):
        """Test concurrent processing performance."""
        # Create multiple image paths
        image_paths = [sample_image_path] * 5

        import time
        start_time = time.time()

        results = await service.batch_extract(
            image_paths,
            [ExtractionType.METADATA],
            max_concurrent=3
        )

        end_time = time.time()
        processing_time = end_time - start_time

        assert len(results) == 5
        assert all(result.success for result in results)
        # Should complete in reasonable time (adjust threshold as needed)
        assert processing_time < 10.0
