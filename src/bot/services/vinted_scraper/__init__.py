"""Simple Vinted Scraper - Minimal, robust scraper with working URLs."""
from .scraper import SimpleVintedScraper, VintedService
from .config import DEFAULT_DOMAIN

__version__ = "2025.08"
__all__ = ["SimpleVintedScraper", "VintedService", "DEFAULT_DOMAIN"]

import logging
logging.getLogger("SimpleVintedScraper").addHandler(logging.NullHandler())