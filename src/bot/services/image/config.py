"""
Configuration module for Image Extraction Service.

Provides centralized configuration management with environment variable support.
"""

import os
from typing import List, Set
from pathlib import Path

# Image Processing Constants
MAX_IMAGE_SIZE_MB = int(os.getenv('IMAGE_MAX_SIZE_MB', '10'))
MAX_IMAGE_DIMENSION = int(os.getenv('IMAGE_MAX_DIMENSION', '4096'))
MIN_IMAGE_DIMENSION = int(os.getenv('IMAGE_MIN_DIMENSION', '10'))
PROCESSING_TIMEOUT = int(os.getenv('EXTRACTION_TIMEOUT', '30'))

# Supported image formats
ALLOWED_FORMATS_STR = os.getenv('ALLOWED_IMAGE_FORMATS', 'jpg,jpeg,png,bmp,tiff,tif,webp')
ALLOWED_FORMATS: Set[str] = {f'.{fmt.lower()}' for fmt in ALLOWED_FORMATS_STR.split(',')}

# OCR Configuration
TESSERACT_LANG = os.getenv('TESSERACT_LANG', 'eng+rus')
TESSERACT_CONFIG = os.getenv('TESSERACT_CONFIG', '--psm 3 --oem 3')

# Cache Configuration
CACHE_DIR = Path(os.getenv('IMAGE_CACHE_DIR', '/tmp/image_extraction_cache'))
CACHE_EXPIRY_HOURS = int(os.getenv('CACHE_EXPIRY_HOURS', '24'))

# Performance Settings
MAX_CONCURRENT_EXTRACTIONS = int(os.getenv('MAX_CONCURRENT_EXTRACTIONS', '3'))

# Quality Settings
DEFAULT_PROCESSING_QUALITY = os.getenv('DEFAULT_PROCESSING_QUALITY', 'BALANCED')

# Security Configuration
def get_security_config():
    """Get security configuration dictionary."""
    return {
        'max_file_size': MAX_IMAGE_SIZE_MB * 1024 * 1024,
        'max_dimension': MAX_IMAGE_DIMENSION,
        'min_dimension': MIN_IMAGE_DIMENSION,
        'allowed_formats': ALLOWED_FORMATS,
    }

def get_tesseract_config():
    """Get Tesseract OCR configuration dictionary."""
    return {
        'lang': TESSERACT_LANG,
        'config': TESSERACT_CONFIG,
    }

def get_cache_config():
    """Get cache configuration."""
    return {
        'cache_dir': CACHE_DIR,
        'expiry_hours': CACHE_EXPIRY_HOURS,
    }

# Validation functions
def validate_config():
    """Validate configuration values."""
    errors = []

    if MAX_IMAGE_SIZE_MB <= 0:
        errors.append("IMAGE_MAX_SIZE_MB must be positive")

    if MAX_IMAGE_DIMENSION <= MIN_IMAGE_DIMENSION:
        errors.append("MAX_IMAGE_DIMENSION must be greater than MIN_IMAGE_DIMENSION")

    if PROCESSING_TIMEOUT <= 0:
        errors.append("EXTRACTION_TIMEOUT must be positive")

    if CACHE_EXPIRY_HOURS < 0:
        errors.append("CACHE_EXPIRY_HOURS cannot be negative")

    if not ALLOWED_FORMATS:
        errors.append("At least one image format must be allowed")

    return errors

# Initialize cache directory
def ensure_cache_directory():
    """Ensure cache directory exists."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create cache directory {CACHE_DIR}: {e}")

# Validate on import
config_errors = validate_config()
if config_errors:
    print("Configuration errors:")
    for error in config_errors:
        print(f"  - {error}")
    print("Please check your environment variables.")

# Ensure cache directory exists
ensure_cache_directory()
