"""
Telegram Bot handlers for image extraction functionality.

Integrates the ImageExtractionService with Telegram bot message handling
for processing user-uploaded images and extracting text/metadata.
"""

import logging
from typing import Optional, List
from pathlib import Path
import tempfile

from aiogram import Router, F
from aiogram.types import Message, PhotoSize, Document
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..services.image import (
    ImageExtractionService,
    ExtractionType,
    ProcessingQuality,
    get_image_extraction_service,
    extract_image_text,
    extract_image_metadata
)
from ..services.image.image_downloader import ImageDownloader
from ..keyboards.reply_keyboards import get_main_keyboard
from src.monitoring import get_logger

logger = get_logger(__name__)
router = Router()

# Global service instance
_extraction_service = get_image_extraction_service()


# REMOVED: General photo handler that was interfering with search results
# Photo analysis should be triggered by specific commands, not all photo messages

@router.message(F.text.startswith("/analyze") | F.text.startswith("анализ") | F.text.startswith("analyze"))
async def handle_analyze_command(message: Message) -> None:
    """
    Handle analyze command for image processing.

    Usage: /analyze or "анализ" - shows instructions
    """
    await message.reply(
        "📸 **Анализ изображений**\n\n"
        "Чтобы проанализировать изображение:\n\n"
        "1️⃣ Отправьте фотографию\n"
        "2️⃣ В подписи напишите: `/analyze` или `анализ`\n\n"
        "🤖 Я смогу:\n"
        "• 📝 Извлечь текст (OCR)\n"
        "• 📊 Показать метаданные\n"
        "• 🔍 Найти объекты на изображении\n\n"
        "💡 Пример: Отправьте фото с подписью `/analyze`\n\n"
        "⚠️ Анализ работает только для изображений с этой командой!"
    )

@router.message(F.photo & (F.caption.startswith("/analyze") | F.caption.startswith("анализ") | F.caption.startswith("analyze")))
async def handle_photo_with_analyze_caption(message: Message) -> None:
    """
    Handle photos with analyze caption for image extraction.
    Only processes images when explicitly requested.
    """
    if not message.photo:
        return

    await message.reply("🔄 Начинаю анализ изображения...")

    # Get the highest quality photo
    photo = message.photo[-1]

    try:
        # Download the image
        async with ImageDownloader() as downloader:
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                temp_path = Path(tmp.name)

            success = await downloader.download_image(
                f"https://api.telegram.org/file/bot{message.bot.token}/getFile?file_id={photo.file_id}",
                temp_path
            )

            if not success:
                await message.reply("❌ Не удалось скачать изображение для анализа.")
                return

            # Process the image with full analysis
            result = await _extraction_service.extract_from_file(
                temp_path,
                [ExtractionType.METADATA, ExtractionType.OCR_TEXT, ExtractionType.OBJECT_DETECTION],
                ProcessingQuality.HIGH  # Use high quality for analysis
            )

            if result.success:
                response_text = await _format_extraction_response(result)
                await message.reply(response_text)
            else:
                await message.reply(
                    f"❌ Анализ изображения не удался: {result.error_message}"
                )

            # Cleanup
            temp_path.unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Photo analysis failed: {e}")
        await message.reply("❌ Произошла ошибка при анализе изображения.")


# REMOVED: Document handler - analysis should be explicit command only
# This prevents automatic processing of all uploaded documents


async def _format_extraction_response(result: 'ExtractionResult') -> str:
    """
    Format extraction results into a readable message.

    Args:
        result: ExtractionResult object

    Returns:
        Formatted message string
    """
    response_parts = ["🎯 **Image Analysis Results**\n"]

    # Metadata section
    if result.metadata:
        meta = result.metadata
        response_parts.append("📊 **Metadata:**")
        response_parts.append(f"• Format: {meta.format}")
        response_parts.append(f"• Dimensions: {meta.width}×{meta.height}")
        response_parts.append(f"• File Size: {meta.file_size:,} bytes")
        response_parts.append(f"• Color Mode: {meta.color_mode}")
        if meta.dpi:
            response_parts.append(f"• DPI: {meta.dpi[0]}×{meta.dpi[1]}")

        # Dominant colors (show first 3)
        if meta.dominant_colors:
            colors_text = ", ".join([f"#{r:02x}{g:02x}{b:02x}" for r, g, b in meta.dominant_colors[:3]])
            response_parts.append(f"• Dominant Colors: {colors_text}")

    # OCR section
    if result.ocr_result and result.ocr_result.text.strip():
        ocr = result.ocr_result
        response_parts.append("\n📝 **Extracted Text:**")
        response_parts.append(f"• Language: {ocr.language}")
        response_parts.append(f"• Confidence: {ocr.confidence:.1f}")
        response_parts.append("• Text:")
        # Split long text into chunks
        text = ocr.text.strip()
        if len(text) > 500:
            text = text[:500] + "..."
        response_parts.append(f"```\n{text}\n```")
    elif result.ocr_result:
        response_parts.append("\n📝 **OCR Results:**\n• No text detected in image")
    # Processing time
    response_parts.append("\n⏱️ **Processing Time:**")
    response_parts.append(f"• Total: {result.processing_time:.2f} seconds")
    return "\n".join(response_parts)


# REMOVED: Callback handlers for image extraction
# Image extraction now works directly without interactive buttons
# Users can use /analyze command or send photos with "анализ" caption


# Utility functions for integration with other bot features
async def extract_text_from_image_url(image_url: str, quality: ProcessingQuality = ProcessingQuality.BALANCED) -> Optional[str]:
    """
    Extract text from image URL for use in other bot features.

    Args:
        image_url: URL of the image to process
        quality: OCR quality level

    Returns:
        Extracted text or None if failed
    """
    try:
        async with ImageDownloader() as downloader:
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                temp_path = Path(tmp.name)

            success = await downloader.download_image(image_url, temp_path)

            if not success:
                logger.warning(f"Failed to download image from {image_url}")
                return None

            text = await extract_image_text(temp_path, quality)

            # Cleanup
            temp_path.unlink(missing_ok=True)

            return text if text.strip() else None

    except Exception as e:
        logger.error(f"Text extraction from URL failed: {e}")
        return None


async def analyze_image_for_bot_context(image_path: Path) -> dict:
    """
    Analyze image and return structured data for bot decision making.

    Args:
        image_path: Path to image file

    Returns:
        Dictionary with analysis results
    """
    try:
        result = await _extraction_service.extract_from_file(
            image_path,
            [ExtractionType.METADATA, ExtractionType.OCR_TEXT, ExtractionType.OBJECT_DETECTION],
            ProcessingQuality.BALANCED
        )

        if not result.success:
            return {"error": result.error_message}

        analysis = {
            "has_text": bool(result.ocr_result and result.ocr_result.text.strip()),
            "text_confidence": result.ocr_result.confidence if result.ocr_result else 0.0,
            "image_size": (result.metadata.width, result.metadata.height) if result.metadata else (0, 0),
            "file_size": result.metadata.file_size if result.metadata else 0,
            "processing_time": result.processing_time,
            "objects_detected": len(result.object_detection.objects) if result.object_detection else 0
        }

        return analysis

    except Exception as e:
        logger.error(f"Image analysis failed: {e}")
        return {"error": str(e)}


# Export the router for inclusion in main bot
__all__ = ["router", "extract_text_from_image_url", "analyze_image_for_bot_context"]
