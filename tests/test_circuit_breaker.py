"""Tests for circuit breaker implementation."""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch
import time

from src.utils.circuit_breaker import (
    CircuitBreaker, CircuitBreakerConfig, CircuitState,
    CircuitBreakerRegistry, get_circuit_breaker
)
from src.exceptions import CircuitBreakerError


class TestCircuitBreakerConfig:
    """Test circuit breaker configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = CircuitBreakerConfig()
        
        assert config.failure_threshold == 5
        assert config.timeout == 60
        assert config.success_threshold == 3
        assert config.expected_exception == (Exception,)
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            timeout=120,
            success_threshold=2,
            expected_exception=(ValueError, TypeError)
        )
        
        assert config.failure_threshold == 3
        assert config.timeout == 120
        assert config.success_threshold == 2
        assert config.expected_exception == (ValueError, TypeError)


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    def test_initial_state(self):
        """Test circuit breaker initial state."""
        cb = CircuitBreaker("test", CircuitBreakerConfig())
        
        assert cb.name == "test"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 0
        assert cb.last_failure_time is None
        assert cb.last_success_time is None
    
    @pytest.mark.asyncio
    async def test_successful_call(self):
        """Test successful function call."""
        cb = CircuitBreaker("test", CircuitBreakerConfig())
        
        async def success_func():
            return "success"
        
        result = await cb.call(success_func)
        
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.last_success_time is not None
    
    @pytest.mark.asyncio
    async def test_sync_function_call(self):
        """Test calling synchronous function."""
        cb = CircuitBreaker("test", CircuitBreakerConfig())
        
        def sync_func():
            return "sync_success"
        
        result = await cb.call(sync_func)
        
        assert result == "sync_success"
        assert cb.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_failure_recording(self):
        """Test failure recording."""
        config = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker("test", config)
        
        async def failing_func():
            raise ValueError("Test error")
        
        # First failure
        with pytest.raises(ValueError):
            await cb.call(failing_func)
        
        assert cb.failure_count == 1
        assert cb.state == CircuitState.CLOSED
        assert cb.last_failure_time is not None
        
        # Second failure - should open circuit
        with pytest.raises(ValueError):
            await cb.call(failing_func)
        
        assert cb.failure_count == 2
        assert cb.state == CircuitState.OPEN
    
    @pytest.mark.asyncio
    async def test_circuit_open_rejection(self):
        """Test circuit breaker rejecting calls when open."""
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("test", config)
        
        async def failing_func():
            raise ValueError("Test error")
        
        # Trigger circuit to open
        with pytest.raises(ValueError):
            await cb.call(failing_func)
        
        assert cb.state == CircuitState.OPEN
        
        # Next call should be rejected
        with pytest.raises(CircuitBreakerError) as exc_info:
            await cb.call(failing_func)
        
        assert "Circuit breaker 'test' is OPEN" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_half_open_transition(self):
        """Test transition from open to half-open state."""
        config = CircuitBreakerConfig(failure_threshold=1, timeout=0.1)
        cb = CircuitBreaker("test", config)
        
        async def failing_func():
            raise ValueError("Test error")
        
        # Open the circuit
        with pytest.raises(ValueError):
            await cb.call(failing_func)
        
        assert cb.state == CircuitState.OPEN
        
        # Wait for timeout
        await asyncio.sleep(0.2)
        
        # Check state transition
        await cb._check_state()
        assert cb.state == CircuitState.HALF_OPEN
    
    @pytest.mark.asyncio
    async def test_half_open_to_closed(self):
        """Test transition from half-open to closed state."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            timeout=0.1,
            success_threshold=2
        )
        cb = CircuitBreaker("test", config)
        
        # Open the circuit
        async def failing_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            await cb.call(failing_func)
        
        # Wait and transition to half-open
        await asyncio.sleep(0.2)
        await cb._check_state()
        assert cb.state == CircuitState.HALF_OPEN
        
        # Successful calls to close circuit
        async def success_func():
            return "success"
        
        await cb.call(success_func)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.success_count == 1
        
        await cb.call(success_func)
        assert cb.state == CircuitState.CLOSED
        assert cb.success_count == 0
        assert cb.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_half_open_to_open(self):
        """Test transition from half-open back to open on failure."""
        config = CircuitBreakerConfig(failure_threshold=1, timeout=0.1)
        cb = CircuitBreaker("test", config)
        
        # Open the circuit
        async def failing_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            await cb.call(failing_func)
        
        # Wait and transition to half-open
        await asyncio.sleep(0.2)
        await cb._check_state()
        assert cb.state == CircuitState.HALF_OPEN
        
        # Failure should reopen circuit
        with pytest.raises(ValueError):
            await cb.call(failing_func)
        
        assert cb.state == CircuitState.OPEN
        assert cb.success_count == 0
    
    @pytest.mark.asyncio
    async def test_expected_exception_filtering(self):
        """Test that only expected exceptions trigger circuit breaker."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            expected_exception=(ValueError,)
        )
        cb = CircuitBreaker("test", config)
        
        # ValueError should trigger circuit breaker
        async def value_error_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            await cb.call(value_error_func)
        
        assert cb.failure_count == 1
        
        # TypeError should not trigger circuit breaker
        async def type_error_func():
            raise TypeError("Type error")
        
        with pytest.raises(TypeError):
            await cb.call(type_error_func)
        
        # Failure count should remain the same
        assert cb.failure_count == 1
    
    def test_get_state(self):
        """Test getting circuit breaker state."""
        config = CircuitBreakerConfig(failure_threshold=3, timeout=120)
        cb = CircuitBreaker("test", config)
        cb.failure_count = 2
        cb.last_failure_time = 1234567890.0
        
        state = cb.get_state()
        
        assert state["name"] == "test"
        assert state["state"] == "closed"
        assert state["failure_count"] == 2
        assert state["last_failure_time"] == 1234567890.0
        assert state["config"]["failure_threshold"] == 3
        assert state["config"]["timeout"] == 120


class TestCircuitBreakerRegistry:
    """Test circuit breaker registry."""
    
    def test_get_breaker_new(self):
        """Test getting new circuit breaker."""
        registry = CircuitBreakerRegistry()
        
        breaker = registry.get_breaker("test")
        
        assert breaker.name == "test"
        assert isinstance(breaker, CircuitBreaker)
    
    def test_get_breaker_existing(self):
        """Test getting existing circuit breaker."""
        registry = CircuitBreakerRegistry()
        
        breaker1 = registry.get_breaker("test")
        breaker2 = registry.get_breaker("test")
        
        assert breaker1 is breaker2
    
    def test_get_breaker_with_config(self):
        """Test getting circuit breaker with custom config."""
        registry = CircuitBreakerRegistry()
        config = CircuitBreakerConfig(failure_threshold=10)
        
        breaker = registry.get_breaker("test", config)
        
        assert breaker.config.failure_threshold == 10
    
    def test_get_all_states(self):
        """Test getting all circuit breaker states."""
        registry = CircuitBreakerRegistry()
        
        breaker1 = registry.get_breaker("test1")
        breaker2 = registry.get_breaker("test2")
        
        states = registry.get_all_states()
        
        assert "test1" in states
        assert "test2" in states
        assert states["test1"]["name"] == "test1"
        assert states["test2"]["name"] == "test2"


class TestGlobalRegistry:
    """Test global circuit breaker registry functions."""
    
    def test_get_circuit_breaker(self):
        """Test getting circuit breaker from global registry."""
        breaker = get_circuit_breaker("global_test")
        
        assert breaker.name == "global_test"
        assert isinstance(breaker, CircuitBreaker)
    
    def test_get_circuit_breaker_with_config(self):
        """Test getting circuit breaker with config from global registry."""
        config = CircuitBreakerConfig(failure_threshold=5)
        breaker = get_circuit_breaker("global_test_config", config)
        
        assert breaker.config.failure_threshold == 5


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_api_call_simulation(self):
        """Test simulating API calls with circuit breaker."""
        config = CircuitBreakerConfig(failure_threshold=3, timeout=0.1)
        cb = CircuitBreaker("api_test", config)
        
        call_count = 0
        
        async def api_call():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise ConnectionError("API unavailable")
            return {"status": "success"}
        
        # First 3 calls should fail and open circuit
        for i in range(3):
            with pytest.raises(ConnectionError):
                await cb.call(api_call)
        
        assert cb.state == CircuitState.OPEN
        
        # Next call should be rejected by circuit breaker
        with pytest.raises(CircuitBreakerError):
            await cb.call(api_call)
        
        # Wait for timeout and try again
        await asyncio.sleep(0.2)
        
        # This should succeed and close the circuit
        result = await cb.call(api_call)
        assert result["status"] == "success"
        assert cb.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_concurrent_calls(self):
        """Test circuit breaker with concurrent calls."""
        config = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker("concurrent_test", config)
        
        async def sometimes_failing_func(should_fail=False):
            if should_fail:
                raise ValueError("Concurrent failure")
            return "success"
        
        # Run concurrent successful calls
        tasks = [cb.call(sometimes_failing_func) for _ in range(5)]
        results = await asyncio.gather(*tasks)
        
        assert all(result == "success" for result in results)
        assert cb.state == CircuitState.CLOSED
        
        # Run concurrent failing calls
        tasks = [cb.call(sometimes_failing_func, should_fail=True) for _ in range(3)]
        
        with pytest.raises(ValueError):
            await asyncio.gather(*tasks, return_exceptions=False)
        
        # Circuit should be open after failures
        assert cb.state == CircuitState.OPEN