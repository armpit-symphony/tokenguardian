"""
Token Guardian Circuit Breaker
Work Order: #TG-MINIMAX-AVAILABILITY-GUARD

Provides circuit breaker pattern for provider availability.
- CLOSED: Normal operation
- OPEN: Provider failing, reject requests
- HALF_OPEN: Testing if provider recovered
"""

import time
from typing import Optional, Dict
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone


class BreakerState(Enum):
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"         # Failing, reject requests
    HALF_OPEN = "HALF_OPEN"  # Testing recovery


@dataclass
class BreakerStats:
    """Statistics for a circuit breaker."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: Optional[str] = None
    last_success_time: Optional[str] = None
    state: BreakerState = BreakerState.CLOSED
    failure_threshold: int = 2
    cooldown_seconds: int = 900  # 15 minutes


@dataclass
class BreakerResult:
    """Result of a circuit breaker operation."""
    allowed: bool
    state: BreakerState
    failover_provider: Optional[str] = None
    reason: Optional[str] = None
    stats: BreakerStats = None


class CircuitBreaker:
    """
    Circuit breaker for provider reliability.
    
    Configuration:
        - failure_threshold: Number of consecutive failures to open breaker
        - cooldown_seconds: Time to wait before trying again
        - failover_provider: Provider to route to when open
    
    Usage:
        breaker = CircuitBreaker(
            failure_threshold=2,
            cooldown_seconds=900,
            failover_provider="openai/gpt-5-mini"
        )
        
        result = breaker.can_proceed("minimax")
        if not result.allowed:
            # Route to failover_provider
    """
    
    # Global registry of breakers per provider
    _breakers: Dict[str, 'CircuitBreaker'] = {}
    
    def __init__(
        self,
        provider: str,
        failure_threshold: int = 2,
        cooldown_seconds: int = 900,
        failover_provider: Optional[str] = None
    ):
        self.provider = provider
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failover_provider = failover_provider
        
        self.state = BreakerState.CLOSED
        self.stats = BreakerStats(
            state=self.state,
            failure_threshold=failure_threshold,
            cooldown_seconds=cooldown_seconds
        )
        
        self._last_failure_time: Optional[float] = None
        self._half_open_successes = 0
    
    @classmethod
    def get_breaker(cls, provider: str, **kwargs) -> 'CircuitBreaker':
        """Get or create a circuit breaker for a provider."""
        if provider not in cls._breakers:
            cls._breakers[provider] = CircuitBreaker(provider, **kwargs)
        return cls._breakers[provider]
    
    @classmethod
    def all_breakers(cls) -> Dict[str, 'CircuitBreaker']:
        """Get all registered breakers."""
        return cls._breakers.copy()
    
    @classmethod
    def reset_all(cls):
        """Reset all circuit breakers (for testing)."""
        cls._breakers.clear()
    
    def can_proceed(self) -> BreakerResult:
        """
        Check if requests can proceed to this provider.
        
        Returns:
            BreakerResult with allowed status, state, and failover info
        """
        # Update state based on cooldown
        self._update_state()
        
        if self.state == BreakerState.CLOSED:
            return BreakerResult(
                allowed=True,
                state=self.state,
                stats=self.stats
            )
        
        elif self.state == BreakerState.OPEN:
            return BreakerResult(
                allowed=False,
                state=self.state,
                failover_provider=self.failover_provider,
                reason=f"COOLDOWN ({self._remaining_cooldown()}s remaining)",
                stats=self.stats
            )
        
        elif self.state == BreakerState.HALF_OPEN:
            # Allow limited requests to test recovery
            return BreakerResult(
                allowed=True,
                state=self.state,
                reason="Testing recovery",
                stats=self.stats
            )
        
        return BreakerResult(allowed=False, state=self.state, stats=self.stats)
    
    def record_success(self):
        """Record a successful request."""
        self.stats.total_requests += 1
        self.stats.successful_requests += 1
        self.stats.consecutive_failures = 0
        self.stats.consecutive_successes += 1
        self.stats.last_success_time = datetime.now(timezone.utc).isoformat()
        
        if self.state == BreakerState.OPEN:
            # Success during cooldown - immediately try HALF_OPEN and count
            self._half_open()
            self._half_open_successes = 1  # This success counts!
        elif self.state == BreakerState.HALF_OPEN:
            # Already testing - increment and check if ready to close
            self._half_open_successes += 1
            if self._half_open_successes >= 2:
                # Enough successes - close the breaker
                self._close()
    
    def record_failure(self, error: str = "Unknown"):
        """Record a failed request."""
        self.stats.total_requests += 1
        self.stats.failed_requests += 1
        self.stats.consecutive_failures += 1
        self.stats.consecutive_successes = 0
        self.stats.last_failure_time = datetime.now(timezone.utc).isoformat()
        
        # Track failure reason in state
        self._last_failure_time = time.time()
        
        if self.state == BreakerState.HALF_OPEN:
            # Failure during test - reopen
            self._open(error)
        
        elif self.state == BreakerState.CLOSED:
            if self.stats.consecutive_failures >= self.failure_threshold:
                self._open(error)
    
    def _update_state(self):
        """Update breaker state based on cooldown."""
        if self.state == BreakerState.OPEN:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.cooldown_seconds:
                # Cooldown expired - try HALF_OPEN
                self._half_open()
    
    def _open(self, reason: str):
        """Open the circuit breaker."""
        self.state = BreakerState.OPEN
        self.stats.state = self.state
        self._last_failure_time = time.time()
        print(f"[CIRCUIT_BREAKER] {self.provider} OPENED - {reason}")
    
    def _close(self):
        """Close the circuit breaker."""
        self.state = BreakerState.CLOSED
        self.stats.state = self.state
        self._half_open_successes = 0
        print(f"[CIRCUIT_BREAKER] {self.provider} CLOSED - Recovered")
    
    def _half_open(self):
        """Enter half-open state to test recovery."""
        # Only transition if not already in HALF_OPEN
        if self.state != BreakerState.HALF_OPEN:
            self.state = BreakerState.HALF_OPEN
            self.stats.state = self.state
            print(f"[CIRCUIT_BREAKER] {self.provider} HALF_OPEN - Testing recovery")
    
    def _remaining_cooldown(self) -> int:
        """Get remaining cooldown time in seconds."""
        if self._last_failure_time is None:
            return 0
        elapsed = time.time() - self._last_failure_time
        remaining = self.cooldown_seconds - elapsed
        return max(0, int(remaining))
    
    def get_status(self) -> dict:
        """Get full status for health check output."""
        return {
            'provider': self.provider,
            'state': self.state.value,
            'consecutive_failures': self.stats.consecutive_failures,
            'cooldown_remaining': f"{self._remaining_cooldown()}s" if self.state == BreakerState.OPEN else "0s",
            'failover_provider': self.failover_provider,
            'total_requests': self.stats.total_requests,
            'success_rate': f"{(self.stats.successful_requests/self.stats.total_requests*100):.1f}%" if self.stats.total_requests > 0 else "N/A"
        }


# Convenience function
def get_breaker(provider: str, **kwargs) -> CircuitBreaker:
    """Get circuit breaker for a provider."""
    return CircuitBreaker.get_breaker(provider, **kwargs)
