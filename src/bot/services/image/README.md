# Image Extraction Service

A comprehensive, production-ready image processing service for the Vinted Telegram Bot that provides local image analysis capabilities including OCR text extraction, object detection, and metadata analysis.

## Features

- **OCR Text Extraction**: Extract text from images using Tesseract OCR
- **Object Detection**: Basic object detection using OpenCV
- **Metadata Analysis**: Comprehensive image metadata extraction
- **Security First**: Built-in security validations and safe file handling
- **Performance Optimized**: Async processing with caching and batch operations
- **Configurable**: Environment-based configuration system
- **Production Ready**: Error handling, logging, and graceful fallbacks

## Installation

### Dependencies

Install the required packages:

```bash
pip install -r requirements_image_processing.txt
```

### System Dependencies

#### Tesseract OCR Engine

**macOS:**
```bash
brew install tesseract tesseract-lang
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-rus
```

**Windows:**
Download and install from: https://github.com/UB-Mannheim/tesseract/wiki

## Configuration

### Environment Variables

Create a `.env` file or set environment variables:

```bash
# Image Processing Settings
IMAGE_MAX_SIZE_MB=10
IMAGE_MAX_DIMENSION=4096
IMAGE_MIN_DIMENSION=10

# OCR Configuration
TESSERACT_LANG=eng+rus
TESSERACT_CONFIG=--psm 3 --oem 3

# Cache Settings
IMAGE_CACHE_DIR=/tmp/image_extraction_cache
CACHE_EXPIRY_HOURS=24

# Performance Settings
MAX_CONCURRENT_EXTRACTIONS=3
EXTRACTION_TIMEOUT=30

# Security Settings
ALLOWED_IMAGE_FORMATS=jpg,jpeg,png,bmp,tiff,tif,webp
```

### Configuration Validation

The service validates configuration on startup. Check for errors in logs if the service fails to initialize.

## Usage

### Basic Usage

```python
from src.bot.services.image import get_image_extraction_service, ExtractionType, ProcessingQuality

# Get service instance
service = get_image_extraction_service()

# Extract from file
result = await service.extract_from_file(
    "/path/to/image.jpg",
    [ExtractionType.OCR_TEXT, ExtractionType.METADATA],
    ProcessingQuality.BALANCED
)

if result.success:
    print(f"Extracted text: {result.ocr_result.text}")
    print(f"Image size: {result.metadata.width}x{result.metadata.height}")
```

### Extract from Bytes

```python
# Extract from image bytes (useful for Telegram file handling)
with open("image.jpg", "rb") as f:
    image_bytes = f.read()

result = await service.extract_from_bytes(
    image_bytes,
    "image.jpg",
    [ExtractionType.ALL]
)
```

### Batch Processing

```python
# Process multiple images concurrently
image_paths = ["/path/image1.jpg", "/path/image2.png", "/path/image3.bmp"]
results = await service.batch_extract(
    image_paths,
    [ExtractionType.METADATA, ExtractionType.OCR_TEXT],
    max_concurrent=5
)

for i, result in enumerate(results):
    if result.success:
        print(f"Image {i+1}: {len(result.ocr_result.text)} characters extracted")
```

### Convenience Functions

```python
from src.bot.services.image import extract_image_text, extract_image_metadata

# Quick text extraction
text = await extract_image_text("/path/to/image.jpg", ProcessingQuality.HIGH)

# Quick metadata extraction
metadata = await extract_image_metadata("/path/to/image.jpg")
if metadata:
    print(f"Dimensions: {metadata.width}x{metadata.height}")
```

## Telegram Bot Integration

### Handler Integration

Add to your bot's main router:

```python
from src.bot.handlers.image_extraction_handlers import router as image_router

# Include in main bot
dp = Dispatcher()
dp.include_router(image_router)
```

### Message Handling

The service automatically handles:

- **Photo messages**: Users can upload photos and choose extraction options
- **Document messages**: Processes image files uploaded as documents
- **Inline keyboards**: Provides user-friendly extraction options

### Custom Integration

```python
from src.bot.handlers.image_extraction_handlers import extract_text_from_image_url

# Extract text from Vinted item images
async def process_vinted_item(item_data: dict):
    if 'photos' in item_data:
        for photo_url in item_data['photos']:
            text = await extract_text_from_image_url(photo_url)
            if text:
                # Process extracted text
                print(f"Found text in image: {text}")
```

## API Reference

### ImageExtractionService

#### Methods

- `extract_from_file(file_path, extraction_types, quality, language, use_cache)`
- `extract_from_bytes(image_bytes, filename, extraction_types, quality, language)`
- `batch_extract(file_paths, extraction_types, quality, language, max_concurrent)`

#### Parameters

- **extraction_types**: List of `ExtractionType` (OCR_TEXT, OBJECT_DETECTION, METADATA, ALL)
- **quality**: `ProcessingQuality` (FAST, BALANCED, HIGH)
- **language**: OCR language code (default: from config)
- **use_cache**: Enable/disable caching (default: True)
- **max_concurrent**: Maximum concurrent extractions (default: from config)

### ExtractionType Enum

- `OCR_TEXT`: Text extraction using OCR
- `OBJECT_DETECTION`: Object detection using OpenCV
- `METADATA`: Image metadata extraction
- `ALL`: All extraction types

### ProcessingQuality Enum

- `FAST`: Quick processing with basic enhancements
- `BALANCED`: Balanced quality and speed (recommended)
- `HIGH`: High-quality processing with advanced enhancements

## Security Features

### File Validation

- **Format validation**: Only allowed image formats are processed
- **Size limits**: Configurable maximum file size and dimensions
- **Path safety**: Prevents directory traversal attacks
- **Content validation**: Verifies image integrity before processing

### Safe File Handling

- **Temporary files**: Secure temporary file creation and cleanup
- **Memory limits**: Prevents memory exhaustion attacks
- **Timeout protection**: Processing timeouts prevent hanging operations

## Performance Optimizations

### Caching

- **Result caching**: Avoids reprocessing identical images
- **Configurable expiry**: Automatic cache cleanup
- **Hash-based keys**: Efficient cache key generation

### Async Processing

- **Non-blocking I/O**: All operations are async-compatible
- **Concurrent processing**: Batch operations with semaphore control
- **Thread pool usage**: CPU-intensive operations run in thread pools

### Memory Management

- **Stream processing**: Large images are processed efficiently
- **Temporary cleanup**: Automatic cleanup of temporary files
- **Resource limits**: Configurable limits prevent resource exhaustion

## Error Handling

### Graceful Degradation

- **Missing dependencies**: Falls back gracefully when Tesseract is unavailable
- **Network failures**: Handles download failures in URL-based operations
- **Corrupted files**: Validates image integrity before processing

### Comprehensive Logging

- **Operation tracking**: Logs all extraction operations
- **Error reporting**: Detailed error messages with context
- **Performance metrics**: Processing time and success rates

## Testing

### Unit Tests

Run the test suite:

```bash
pytest tests/unit/test_image_extraction.py -v
```

### Test Coverage

Tests cover:

- Security validation functions
- Metadata extraction accuracy
- OCR text extraction (with fallback handling)
- Batch processing concurrency
- Cache functionality
- Error handling and edge cases

### Integration Tests

```bash
pytest tests/integration/ -k image -v
```

## Troubleshooting

### Common Issues

1. **Tesseract not found**:
   ```bash
   # Install Tesseract system-wide
   # Check installation: tesseract --version
   ```

2. **Import errors**:
   ```bash
   pip install -r requirements_image_processing.txt
   ```

3. **Permission errors**:
   ```bash
   # Ensure cache directory is writable
   mkdir -p /tmp/image_extraction_cache
   chmod 755 /tmp/image_extraction_cache
   ```

4. **Memory issues**:
   - Reduce `IMAGE_MAX_DIMENSION` in config
   - Use `ProcessingQuality.FAST` for large images
   - Enable cache to avoid reprocessing

### Debug Mode

Enable detailed logging:

```python
import logging
logging.getLogger('src.bot.services.image').setLevel(logging.DEBUG)
```

## Examples

### Complete Telegram Handler

```python
from aiogram import Router, F
from aiogram.types import Message

from src.bot.services.image import (
    get_image_extraction_service,
    ExtractionType,
    ProcessingQuality
)

router = Router()
service = get_image_extraction_service()

@router.message(F.photo)
async def handle_image(message: Message):
    # Get highest quality photo
    photo = message.photo[-1]

    # Download and process
    # (Implementation depends on your download logic)

    result = await service.extract_from_file(
        downloaded_file_path,
        [ExtractionType.OCR_TEXT, ExtractionType.METADATA]
    )

    if result.success and result.ocr_result:
        await message.reply(f"Extracted text: {result.ocr_result.text}")
    else:
        await message.reply("Could not extract text from image")
```

### Vinted Item Processing

```python
async def analyze_vinted_images(item: dict):
    """Analyze images from Vinted item data."""
    from src.bot.services.image import analyze_image_for_bot_context

    if 'photos' in item:
        for photo_url in item['photos']:
            # Download image (implement your download logic)
            # ...

            analysis = await analyze_image_for_bot_context(image_path)
            if analysis.get('has_text'):
                print(f"Image contains text with {analysis['text_confidence']:.2f} confidence")
```

## Contributing

1. Follow the existing code style and patterns
2. Add tests for new features
3. Update documentation for API changes
4. Ensure security validations are maintained
5. Test with various image formats and sizes

## License

This service is part of the Vinted Parser Bot project.
