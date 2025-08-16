# Implementation Plan

- [x] 1. Set up project structure and core configuration
  - Create directory structure following the established layout (src/bot/, src/db/, src/tasks/, tests/)
  - Implement Pydantic settings configuration with environment variable loading
  - Create pyproject.toml with all required dependencies and development tools
  - Set up Docker configuration with multi-stage build and non-root user
  - _Requirements: 6.1, 6.2, 6.3_

- [x] 2. Implement database models and migrations
- [x] 2.1 Create SQLAlchemy models for core entities
  - Write User, Item, Photo, SavedSearch, Referral, and Payment models with proper relationships
  - Add database constraints, indexes, and foreign key relationships
  - Implement created_at/updated_at timestamps with automatic updates
  - _Requirements: 1.3, 3.3, 4.3_

- [x] 2.2 Create Supabase migration files
  - Write SQL migration files for all tables with proper constraints
  - Add indexes for frequently queried columns (tg_id, item_id, user_id)
  - Implement Row Level Security policies for data protection
  - _Requirements: 8.2, 8.5_

- [x] 2.3 Implement database connection and session management
  - Create async SQLAlchemy engine with connection pooling
  - Implement database session factory with proper cleanup
  - Add database health check endpoint for monitoring
  - _Requirements: 6.4, 7.3_

- [x] 3. Build core services layer
- [x] 3.1 Implement User service with trial management
  - Create UserService class with CRUD operations for users
  - Implement trial period calculation and extension logic
  - Add referral linking and bonus award functionality
  - Write unit tests for user creation, referral processing, and trial management
  - _Requirements: 1.1, 1.2, 1.3, 3.2, 3.3_

- [x] 3.2 Implement Vinted API integration service
  - Create VintedService class using vinted-api-wrapper with Austrian domain
  - Implement search functionality with country_ids=14 for Austria shipping
  - Add item detail fetching with full photo arrays
  - Implement rate limiting with aiometer (30 req/min) and retry logic with exponential backoff
  - Write unit tests with mocked Vinted API responses
  - _Requirements: 2.1, 2.2, 2.5, 6.1, 6.3_

- [x] 3.3 Implement payment service with YooKassa integration
  - Create PaymentService class with YooKassa API v3 integration
  - Implement payment creation with redirect confirmation flow
  - Add webhook signature verification using HMAC
  - Implement payment status updates and user subscription extension
  - Write unit tests for payment flows and webhook processing
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 8.3_

- [-] 4. Create Telegram bot handlers
- [x] 4.1 Implement start command handler with referral processing
  - Create /start handler that creates new users with 7-day trial
  - Implement deep link parsing with HMAC signature verification
  - Add referral bonus logic (3 days) with duplicate prevention
  - Implement user greeting with trial status display
  - Write unit tests for user creation, referral processing, and edge cases
  - _Requirements: 1.1, 1.2, 1.4, 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 4.2 Implement search command handler
  - Create search handler that validates user trial/subscription status
  - Implement immediate response with background job queuing
  - Add search result formatting with item details and inline keyboards
  - Implement item detail view with all photos and Vinted link
  - Write unit tests for search flows and result formatting
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 4.3 Implement payment command handlers
  - Create payment initiation handler with YooKassa integration
  - Implement payment confirmation and failure handling
  - Add subscription status display and renewal options
  - Create webhook handler for YooKassa payment notifications
  - Write unit tests for payment flows and webhook processing
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 4.4 Implement referral command handler
  - Create /invite handler that generates signed deep links
  - Implement referral statistics display (count, trial extension)
  - Add referral link sharing with proper formatting
  - Write unit tests for link generation and statistics display
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 5. Build background processing system
- [x] 5.1 Implement async task queue with Redis
  - Create task queue system using Redis for job storage
  - Implement job serialization and deserialization
  - Add job retry logic with exponential backoff
  - Create worker process for background job execution
  - Write unit tests for task queuing and processing
  - _Requirements: 2.5, 6.1, 6.2_

- [x] 5.2 Implement Vinted crawling background jobs
  - Create crawl job that processes search queries asynchronously
  - Implement batch processing for item details fetching
  - Add database batch writes for items and photos
  - Implement job deduplication using Redis SETNX
  - Write unit tests for crawling jobs and batch processing
  - _Requirements: 2.5, 6.1, 6.3, 6.4_

- [x] 5.3 Implement notification system
  - Create notification service for saved search alerts
  - Implement new item matching against user saved searches
  - Add batch notification sending with rate limiting
  - Create subscription expiry notification job
  - Write unit tests for notification matching and sending
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [-] 6. Implement FastAPI web application
- [x] 6.1 Create FastAPI application with webhook endpoints
  - Set up FastAPI app with proper middleware and error handling
  - Implement Telegram webhook endpoint with signature verification
  - Add YooKassa webhook endpoint with HMAC verification
  - Create health check endpoint for monitoring
  - Write unit tests for webhook processing and error handling
  - _Requirements: 6.1, 6.4, 7.1, 7.2, 8.1_

- [x] 6.2 Implement rate limiting and security middleware
  - Add Redis-based rate limiting for API endpoints
  - Implement request logging with structured format
  - Add CORS and security headers middleware
  - Create request ID tracking for observability
  - Write unit tests for rate limiting and security features
  - _Requirements: 6.3, 7.1, 7.2, 8.1, 8.4_

- [x] 6.3 Add monitoring and observability endpoints
  - Create /metrics endpoint for Prometheus monitoring
  - Implement structured logging with user_id, request_id, and duration
  - Add error tracking and alerting integration
  - Create database and Redis health checks
  - Write unit tests for monitoring endpoints and logging
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 7. Implement security and error handling
- [x] 7.1 Add comprehensive error handling
  - Create custom exception hierarchy for different error types
  - Implement global error handlers with user-friendly messages
  - Add circuit breaker pattern for external API calls
  - Implement graceful degradation for service failures
  - Write unit tests for error scenarios and recovery
  - _Requirements: 6.4, 7.3, 8.4_

- [x] 7.2 Implement security measures
  - Add input validation using Pydantic models for all user inputs
  - Implement HMAC signature verification for webhooks
  - Add SQL injection prevention with parameterized queries
  - Create secure session management and token handling
  - Write security tests for injection attacks and validation bypass
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 8. Create comprehensive test suite
- [x] 8.1 Write unit tests for core services
  - Create test fixtures for database models and API responses
  - Write comprehensive tests for UserService, VintedService, and PaymentService
  - Add tests for referral logic, trial management, and payment processing
  - Implement mocking for external APIs (Vinted, YooKassa)
  - Achieve 90%+ code coverage for service layer
  - _Requirements: All requirements through service layer testing_

- [x] 8.2 Write integration tests for bot handlers
  - Create integration tests using aiogram-tests framework
  - Test complete user flows from /start to payment completion
  - Add tests for webhook processing and background job execution
  - Test error scenarios and edge cases
  - Verify database state changes after handler execution
  - _Requirements: All requirements through handler integration testing_

- [x] 8.3 Implement end-to-end testing
  - Create E2E tests with real Telegram bot in test environment
  - Test complete user journeys including referrals and payments
  - Add performance tests for concurrent user scenarios
  - Test deployment and rollback procedures
  - Verify monitoring and alerting functionality
  - _Requirements: All requirements through complete system testing_

- [ ] 9. Setup deployment and operations
- [ ] 9.1 Create deployment configuration
  - Set up GitHub Actions CI/CD pipeline with testing and deployment
  - Create production Docker configuration with security hardening
  - Implement database migration automation in deployment pipeline
  - Add environment-specific configuration management
  - Write deployment documentation and runbooks
  - _Requirements: 6.1, 6.2, 7.4, 8.1_

- [ ] 9.2 Implement monitoring and alerting
  - Set up Prometheus metrics collection and Grafana dashboards
  - Create alerting rules for system health and performance
  - Implement log aggregation and analysis
  - Add uptime monitoring and incident response procedures
  - Create operational documentation and troubleshooting guides
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [ ] 10. Final integration and launch preparation
- [ ] 10.1 Perform system integration testing
  - Test complete system with all components running
  - Verify all external integrations (Telegram, Vinted, YooKassa, Supabase)
  - Load test the system with expected user volumes
  - Validate security measures and data protection compliance
  - Complete final code review and documentation
  - _Requirements: All requirements final validation_

- [ ] 10.2 Prepare for production launch
  - Set up production environment with proper security configuration
  - Configure monitoring, logging, and alerting for production
  - Create backup and disaster recovery procedures
  - Prepare launch communication and user onboarding materials
  - Conduct final security audit and penetration testing
  - _Requirements: 7.4, 8.1, 8.2, 8.4, 8.5_