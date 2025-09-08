"""Session creation and configuration utilities."""
import random
import logging
import urllib3
from urllib3.exceptions import InsecureRequestWarning
import requests

from .config import UA_DESKTOP, UA_MOBILE, DEFAULT_HEADERS

log = logging.getLogger("VintedSessionUtils")

def select_user_agent(mobile: bool) -> str:
    """Select appropriate user agent."""
    return random.choice(UA_MOBILE if mobile else UA_DESKTOP)

def disable_ssl_warnings():
    """Disable SSL warnings for insecure requests."""
    urllib3.disable_warnings(InsecureRequestWarning)

def create_browser_config(mobile: bool) -> dict:
    """Create browser configuration for cloudscraper."""
    return {
        "browser": "chrome",
        "platform": "darwin", 
        "desktop": not mobile
    }

def create_scraper_session(mobile: bool) -> requests.Session:
    """Create requests session (fallback when cloudscraper unavailable)."""
    try:
        import cloudscraper
        browser_config = create_browser_config(mobile)
        session = cloudscraper.create_scraper(browser=browser_config, delay=None)
        return session
    except ImportError:
        log.warning("cloudscraper not available, using requests.Session")
        session = requests.Session()
        return session

def configure_session_ssl(session: requests.Session, verify_ssl: bool):
    """Configure SSL verification for session."""
    session.verify = verify_ssl
    if not verify_ssl:
        # Also disable hostname checking for requests
        import ssl
        import socket
        try:
            # For requests with urllib3 - create custom adapter
            from requests.adapters import HTTPAdapter
            from urllib3.util.ssl_ import create_urllib3_context
            
            class NoSSLAdapter(HTTPAdapter):
                def init_poolmanager(self, *args, **kwargs):
                    ctx = create_urllib3_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    kwargs['ssl_context'] = ctx
                    return super().init_poolmanager(*args, **kwargs)
            
            session.mount('https://', NoSSLAdapter())
        except ImportError:
            pass

def build_session_headers(user_agent: str) -> dict:
    """Build headers for session."""
    headers = DEFAULT_HEADERS.copy()
    headers.update({
        "User-Agent": user_agent,
        "Referer": "https://www.vinted.at/",
        "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "DNT": "1",
        "Sec-Fetch-User": "?1",
    })
    return headers

def update_session_headers(session: requests.Session, headers: dict):
    """Update session headers."""
    session.headers.update(headers)