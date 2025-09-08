# Requirements Document

## Introduction

This feature enhances the existing image extraction service to provide a more comprehensive and robust experience for Vinted bot users. The enhancement focuses on maximizing image display (up to 10 images per item), improving location extraction accuracy, and adding reliable upload date extraction. The goal is to create a "strong powerful" implementation that works entirely without external APIs, using only the existing project structure.

## Requirements

### Requirement 1: Enhanced Image Extraction

**User Story:** As a bot user, I want to see up to 10 high-quality images for each Vinted item, so that I can better evaluate products before making purchasing decisions.

#### Acceptance Criteria

1. WHEN a Vinted item is processed THEN the system SHALL extract and display up to 10 images per item
2. WHEN multiple image sources are available THEN the system SHALL prioritize higher resolution images over thumbnails
3. WHEN image URLs are extracted THEN the system SHALL validate and filter out broken or invalid URLs
4. WHEN creating media groups THEN the system SHALL handle both single images and multi-image groups seamlessly
5. IF fewer than 10 images are available THEN the system SHALL display all available valid images
6. WHEN images fail to load THEN the system SHALL gracefully fallback to available images without breaking the display

### Requirement 2: Robust Location Extraction

**User Story:** As a bot user, I want to see accurate location information for each item, so that I can understand shipping costs and delivery times.

#### Acceptance Criteria

1. WHEN processing a Vinted item THEN the system SHALL extract location information from multiple data sources
2. WHEN user location data is available THEN the system SHALL prioritize city over country information
3. WHEN location extraction encounters nested data structures THEN the system SHALL traverse all possible location fields
4. IF no specific location is found THEN the system SHALL display "Местоположение: Не указано" as fallback
5. WHEN location is successfully extracted THEN the system SHALL format it consistently as "📍 Местоположение: [location]"
6. WHEN multiple location fields exist THEN the system SHALL choose the most specific available location

### Requirement 3: Upload Date Extraction and Formatting

**User Story:** As a bot user, I want to see when each item was uploaded, so that I can prioritize newer listings and understand item freshness.

#### Acceptance Criteria

1. WHEN processing a Vinted item THEN the system SHALL extract upload date from available timestamp fields
2. WHEN timestamp data is available THEN the system SHALL convert it to readable DD.MM.YYYY format
3. WHEN multiple date fields exist THEN the system SHALL prioritize creation date over modification date
4. IF no upload date is available THEN the system SHALL omit the date field rather than showing incorrect information
5. WHEN date conversion fails THEN the system SHALL log the error and continue processing without the date
6. WHEN displaying dates THEN the system SHALL use the format "⏰ Загружено: DD.MM.YYYY"

### Requirement 4: Enhanced Error Handling and Resilience

**User Story:** As a bot user, I want the system to work reliably even when some data is missing or corrupted, so that I always receive useful search results.

#### Acceptance Criteria

1. WHEN any extraction process fails THEN the system SHALL continue processing other data fields
2. WHEN image extraction fails THEN the system SHALL still display text information with location and date
3. WHEN location extraction fails THEN the system SHALL still display images and other available data
4. WHEN date extraction fails THEN the system SHALL still display images and location data
5. WHEN all extractions succeed THEN the system SHALL display complete item information with all enhancements
6. WHEN processing multiple items THEN individual item failures SHALL NOT affect other items in the batch

### Requirement 5: Performance and Resource Management

**User Story:** As a system administrator, I want the enhanced extraction to be performant and resource-efficient, so that the bot can handle multiple concurrent users without degradation.

#### Acceptance Criteria

1. WHEN processing multiple items THEN the system SHALL maintain existing concurrency controls
2. WHEN extracting images THEN the system SHALL respect the MAX_IMAGES_PER_GROUP limit of 10
3. WHEN processing large batches THEN the system SHALL use existing timeout mechanisms
4. WHEN memory usage increases THEN the system SHALL clean up temporary resources appropriately
5. WHEN network requests are needed THEN the system SHALL use existing session management
6. WHEN logging extraction activities THEN the system SHALL use appropriate log levels to avoid spam