"""Session management for Vinted scraper."""
from __future__ import annotations
import logging
import time
from datetime import datetime
from typing import Optional
import requests

from .session_utils import (
    select_user_agent, disable_ssl_warnings, create_scraper_session,
    configure_session_ssl, build_session_headers, update_session_headers
)
from .session_tester import (
    test_session_connection, calculate_expiry_time, reset_backoff,
    log_session_success, log_session_failure
)
from .request_handlers import (
    make_http_request, is_success_status, is_rate_limited, is_auth_error,
    handle_rate_limit, is_ssl_error, calculate_retry_delay,
    log_request_error, log_ssl_error, log_network_error
)
from .config import MAX_RETRY_ATTEMPTS

log = logging.getLogger("VintedSessionManager")

class SessionManager:
    """Manages HTTP sessions for Vinted scraping."""
    
    def __init__(self, base_url: str, mobile: bool = False, verify_ssl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.mobile = mobile
        self.verify_ssl = verify_ssl
        self.session: Optional[requests.Session] = None
        self.session_expires_at: Optional[datetime] = None
        self.backoff = None
        
        if not verify_ssl:
            disable_ssl_warnings()

    def create_session(self) -> None:
        """Create new session with configuration."""
        user_agent = select_user_agent(self.mobile)

        self.session = create_scraper_session(self.mobile)
        configure_session_ssl(self.session, self.verify_ssl)

        headers = build_session_headers(user_agent)
        update_session_headers(self.session, headers)

        # First visit the main page to get proper cookies
        try:
            initial_response = self.session.get(self.base_url, timeout=10)
            if initial_response.status_code == 200:
                log.info("Successfully established initial connection to Vinted")
            else:
                log.warning("Initial connection returned status %d", initial_response.status_code)
        except Exception as e:
            log.warning("Failed to establish initial connection: %s", e)

        if test_session_connection(self.session, self.base_url):
            self._finalize_successful_session(user_agent)
        else:
            log_session_failure(Exception("Connection test failed"))

    def _finalize_successful_session(self, user_agent: str):
        """Finalize successful session creation."""
        self.session_expires_at = calculate_expiry_time()
        self.backoff = reset_backoff()
        log_session_success(user_agent, self.verify_ssl)

    def is_session_expired(self) -> bool:
        """Check if session needs renewal."""
        return (
            self.session is None
            or self.session_expires_at is None
            or datetime.utcnow() >= self.session_expires_at
        )

    def ensure_session(self) -> None:
        """Ensure we have a valid session."""
        if self.is_session_expired():
            self.create_session()

    def make_request(self, url: str, params: dict = None) -> Optional[requests.Response]:
        """Make request with retry logic."""
        self.ensure_session()
        
        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            try:
                response = make_http_request(self.session, url, params)
                result = self._handle_response(response, attempt)
                if result is not None:
                    return result
                    
            except Exception as exc:
                if self._should_abort_on_exception(exc, attempt):
                    return None
                self._handle_retry_exception(exc, attempt)
                
        return None

    def _handle_response(self, response: requests.Response, attempt: int) -> Optional[requests.Response]:
        """Handle HTTP response."""
        if is_success_status(response.status_code):
            return response
            
        if is_rate_limited(response.status_code):
            self.backoff = handle_rate_limit(self.backoff)
            return None
            
        if is_auth_error(response.status_code):
            self.create_session()
            return None
            
        log_request_error(response.status_code, response.text)
        return None

    def _should_abort_on_exception(self, exc: Exception, attempt: int) -> bool:
        """Check if exception should abort retry loop."""
        if is_ssl_error(exc):
            log_ssl_error(exc, attempt)
            # Try to recreate session without SSL verification
            if self.verify_ssl:
                log.warning("SSL error detected, switching to no SSL verification")
                self.verify_ssl = False
                self.create_session()
                return False  # Don't abort, try again with SSL disabled
            return True
        return False

    def _handle_retry_exception(self, exc: Exception, attempt: int):
        """Handle exception that allows retry."""
        log_network_error(exc, attempt, MAX_RETRY_ATTEMPTS)
        delay = calculate_retry_delay(attempt)
        time.sleep(delay)

    def close(self) -> None:
        """Close session and cleanup."""
        if self.session:
            self.session.close()
        self.session = None
        self.session_expires_at = None