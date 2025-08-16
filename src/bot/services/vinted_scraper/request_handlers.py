"""HTTP request handling utilities."""
import time
import random
import logging
import requests
from requests.exceptions import SSLError, RequestException
from .config import REQUEST_TIMEOUT, BASE_BACKOFF

log = logging.getLogger("VintedRequestHandlers")

def make_http_request(session: requests.Session, url: str, params: dict = None) -> requests.Response:
    """Make HTTP GET request."""
    return session.get(url, params=params, timeout=REQUEST_TIMEOUT)

def is_success_status(status_code: int) -> bool:
    """Check if status code indicates success."""
    return status_code == 200

def is_rate_limited(status_code: int) -> bool:
    """Check if request was rate limited."""
    return status_code == 429

def is_auth_error(status_code: int) -> bool:
    """Check if request has auth error."""
    return status_code in (401, 403)

def handle_rate_limit(backoff: int) -> int:
    """Handle rate limiting with backoff."""
    time.sleep(backoff + random.random())
    return backoff * 2

def is_ssl_error(exception: Exception) -> bool:
    """Check if exception is SSL-related."""
    return isinstance(exception, SSLError)

def calculate_retry_delay(attempt: int) -> float:
    """Calculate delay for retry attempt."""
    return BASE_BACKOFF * attempt

def log_request_error(status_code: int, response_text: str):
    """Log request error."""
    log.error("Request failed %s: %.120s", status_code, response_text)

def log_ssl_error(error: Exception, attempt: int):
    """Log SSL error."""
    log.error("Unrecoverable SSL error: %s → give up after %d attempt(s)", error, attempt)

def log_network_error(error: Exception, attempt: int, max_retry: int):
    """Log network error."""
    log.warning("Network error (%s) retry %d/%d", error, attempt, max_retry)