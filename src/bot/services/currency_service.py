"""Currency conversion service for real-time EUR to RUB conversion."""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from functools import lru_cache

try:
    from forex_python.converter import CurrencyRates, RatesNotAvailableError
    FOREX_AVAILABLE = True
except ImportError:
    FOREX_AVAILABLE = False
    # Create dummy classes for fallback
    class CurrencyRates:
        def get_rate(self, from_curr, to_curr):
            raise RatesNotAvailableError("Forex service unavailable")

    class RatesNotAvailableError(Exception):
        pass

from src.monitoring import get_logger

logger = get_logger(__name__)


class CurrencyService:
    """Service for real-time currency conversion with caching."""

    def __init__(self, cache_duration_minutes: int = 30):
        """Initialize currency service with cache settings."""
        self.cache_duration = timedelta(minutes=cache_duration_minutes)
        self._rates_cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._forex_available = FOREX_AVAILABLE
        self._converter = CurrencyRates() if FOREX_AVAILABLE else None

    def _is_cache_valid(self) -> bool:
        """Check if cached rates are still valid."""
        if self._cache_timestamp is None:
            return False
        return datetime.now() - self._cache_timestamp < self.cache_duration

    def _get_cached_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Get cached exchange rate."""
        if not self._is_cache_valid() or not self._rates_cache:
            return None

        try:
            # Try to get rate from cache
            rate = self._converter.get_rate(from_currency, to_currency)
            logger.debug(f"Using cached rate: 1 {from_currency} = {rate} {to_currency}")
            return rate
        except Exception:
            return None

    async def _fetch_fresh_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Fetch fresh exchange rate from web API."""
        try:
            # Get fresh rate from web API
            rate = self._converter.get_rate(from_currency, to_currency)

            # Update cache
            self._rates_cache = {f"{from_currency}_{to_currency}": rate}
            self._cache_timestamp = datetime.now()

            logger.info(f"Fetched fresh rate: 1 {from_currency} = {rate} {to_currency}")
            return rate

        except RatesNotAvailableError as e:
            logger.error(f"Currency rates not available: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching currency rate: {e}")
            return None

    async def convert_eur_to_rub(self, amount_eur: float) -> Optional[float]:
        """Convert EUR amount to RUB using real-time rates."""
        if amount_eur <= 0:
            return amount_eur

        # If forex is not available, return None to trigger fallback
        if not self._forex_available:
            logger.warning("Forex service not available, skipping conversion")
            return None

        try:
            # Try cached rate first
            rate = self._get_cached_rate('EUR', 'RUB')

            # If no cached rate, fetch fresh one
            if rate is None:
                rate = await self._fetch_fresh_rate('EUR', 'RUB')

            if rate is None:
                logger.warning("Could not get EUR to RUB exchange rate")
                return None

            # Convert amount
            amount_rub = amount_eur * rate

            logger.debug(".2f")
            return round(amount_rub, 2)

        except Exception as e:
            logger.error(f"Error converting {amount_eur} EUR to RUB: {e}")
            return None

    async def get_exchange_rate(self, from_currency: str = 'EUR', to_currency: str = 'RUB') -> Optional[float]:
        """Get current exchange rate between two currencies."""
        try:
            # Try cached rate first
            rate = self._get_cached_rate(from_currency, to_currency)

            # If no cached rate, fetch fresh one
            if rate is None:
                rate = await self._fetch_fresh_rate(from_currency, to_currency)

            return rate

        except Exception as e:
            logger.error(f"Error getting {from_currency} to {to_currency} rate: {e}")
            return None

    async def format_price_with_rub(self, amount_eur: float, include_original: bool = True) -> str:
        """Format price with both EUR and RUB."""
        if amount_eur <= 0:
            return f"{amount_eur:.2f} EUR"

        amount_rub = await self.convert_eur_to_rub(amount_eur)

        if amount_rub is None:
            # Fallback to EUR only if conversion fails
            return f"{amount_eur:.2f} EUR"

        if include_original:
            return f"{amount_eur:.2f} EUR (~{amount_rub:.0f} ₽)"
        else:
            return f"{amount_rub:.0f} ₽"


# Global instance
_currency_service = None


def get_currency_service() -> CurrencyService:
    """Get global currency service instance."""
    global _currency_service
    if _currency_service is None:
        _currency_service = CurrencyService()
    return _currency_service


async def convert_eur_to_rub(amount: float) -> Optional[float]:
    """Convenience function to convert EUR to RUB."""
    service = get_currency_service()
    return await service.convert_eur_to_rub(amount)


async def format_price_with_rub(amount_eur: float, include_original: bool = True) -> str:
    """Convenience function to format price with RUB conversion."""
    service = get_currency_service()
    return await service.format_price_with_rub(amount_eur, include_original)
