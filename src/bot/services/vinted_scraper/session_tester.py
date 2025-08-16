"""Session testing and validation."""
import logging
from datetime import datetime
import requests
from .config import REQUEST_TIMEOUT, SESSION_LIFETIME, BASE_BACKOFF

log = logging.getLogger("VintedSessionTester")

def test_session_connection(session: requests.Session, base_url: str) -> bool:
    """Test if session can connect to base URL."""
    try:
        response = session.get(base_url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return True
    except Exception as e:
        log.error("Session test failed: %s", e)
        return False

def calculate_expiry_time() -> datetime:
    """Calculate session expiry time."""
    return datetime.utcnow() + SESSION_LIFETIME

def reset_backoff() -> int:
    """Reset backoff to default value."""
    return BASE_BACKOFF

def log_session_success(user_agent: str, verify_ssl: bool):
    """Log successful session creation."""
    log.info("New session established (UA=%s, verify_ssl=%s)", user_agent, verify_ssl)

def log_session_failure(error: Exception):
    """Log session creation failure."""
    log.error("Failed to create session: %s", error)