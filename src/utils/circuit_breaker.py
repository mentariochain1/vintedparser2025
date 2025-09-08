"""
Circuit breaker pattern implementation for external API calls.

Provides automatic failure detection and recovery for external services
like Vinted API, YooKassa, and Telegram API.
"""

import asyncio
import time
from enum import Enum
from typing import Callable, Any, Optional, Dict
from dataclasses import dataclass
import logging

from src.exceptions import CircuitBreakerError, ServiceUnavailableError

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, rejecting calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5  # Failures before opening
    timeout: int = 60  # Seconds to wait before trying again
    success_threshold: int = 3  # Successes needed to close from half-open
    expected_exception: tuple = (Exception,)  # Exceptions that count as failures


class CircuitBreaker:
    """
    Circuit breaker for external API calls.
    
    Automatically opens when failure threshold is reached,
    and attempts recovery after timeout period.
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.last_success_time: Optional[float] = None
        
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerError: When circuit is open
            Original exception: When function fails
        """
        async with self._lock:
            await self._check_state()
            
            if self.state == CircuitState.OPEN:
                raise CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is OPEN. Service unavailable.",
                    details={
                        "failure_count": self.failure_count,
                        "last_failure_time": self.last_failure_time,
                        "timeout": self.config.timeout
                    }
                )
        
        try:
            # Execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Record success
            await self._record_success()
            return result
            
        except self.config.expected_exception as e:
            # Record failure
            await self._record_failure(e)
            raise
    
    async def _check_state(self):
        """Check and update circuit breaker state."""
        current_time = time.time()
        
        if self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if (self.last_failure_time and 
                current_time - self.last_failure_time >= self.config.timeout):
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info(f"Circuit breaker '{self.name}' moved to HALF_OPEN")
    
    async def _record_success(self):
        """Record successful call."""
        async with self._lock:
            self.last_success_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
                    logger.info(f"Circuit breaker '{self.name}' moved to CLOSED")
            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.failure_count = 0
    
    async def _record_failure(self, exception: Exception):
        """Record failed call."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            logger.warning(
                f"Circuit breaker '{self.name}' recorded failure {self.failure_count}/{self.config.failure_threshold}",
                extra={
                    "exception": str(exception),
                    "exception_type": type(exception).__name__
                }
            )
            
            if (self.state == CircuitState.CLOSED and 
                self.failure_count >= self.config.failure_threshold):
                self.state = CircuitState.OPEN
                logger.error(f"Circuit breaker '{self.name}' moved to OPEN")
            elif self.state == CircuitState.HALF_OPEN:
                # Any failure in half-open state reopens the circuit
                self.state = CircuitState.OPEN
                self.success_count = 0
                logger.error(f"Circuit breaker '{self.name}' moved back to OPEN")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "timeout": self.config.timeout,
                "success_threshold": self.config.success_threshold
            }
        }


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
    
    def get_breaker(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """Get or create a circuit breaker."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]
    
    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get states of all circuit breakers."""
        return {name: breaker.get_state() for name, breaker in self._breakers.items()}


# Global registry instance
circuit_breaker_registry = CircuitBreakerRegistry()


def get_circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
    """Get a circuit breaker from the global registry."""
    return circuit_breaker_registry.get_breaker(name, config)