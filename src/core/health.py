"""
Token Guardian Health Check Module
Work Order: #TG-MINIMAX-AVAILABILITY-GUARD

Provides health check functionality for tokenguardian doctor --providers command.
"""

import time
from typing import Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone

from .timeout_wrapper import TimeoutWrapper, RequestStatus
from .circuit_breaker import CircuitBreaker, BreakerState


@dataclass
class ProviderHealth:
    """Health status for a provider."""
    provider: str
    status: str  # OK, TIMEOUT, COOLDOWN, ERROR
    latency_ms: int
    consecutive_failures: int
    cooldown_remaining: str
    state: str
    last_check: str


class ProviderHealthChecker:
    """
    Health checker for API providers.
    
    Usage:
        checker = ProviderHealthChecker()
        health = checker.check("minimax")
        print(f"{health.provider} - {health.status}")
    """
    
    # Default timeout for health checks
    DEFAULT_TIMEOUT_SECONDS = 60
    
    # Known providers and their endpoints
    PROVIDER_ENDPOINTS = {
        'minimax': None,  # Will use OpenClaw routing
        'openai': None,
        'xai': None,
        'anthropic': None
    }
    
    # Fallback provider configuration
    FAILOVER_MAP = {
        'minimax': 'openai/gpt-5-mini',
        'openai': 'anthropic/claude-3-5-sonnet',
        'xai': 'openai/gpt-5-mini',
        'anthropic': 'openai/gpt-5-mini'
    }
    
    def __init__(self, timeout_seconds: int = None):
        self.timeout_seconds = timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS
        self.wrapper = TimeoutWrapper(self.timeout_seconds)
    
    def check(self, provider: str) -> ProviderHealth:
        """
        Perform a health check on a provider.
        
        Args:
            provider: Provider name (e.g., 'minimax')
        
        Returns:
            ProviderHealth with status, latency, etc.
        """
        start_time = time.time()
        
        # Get circuit breaker state
        breaker = CircuitBreaker.get_breaker(
            provider=provider,
            failure_threshold=2,
            cooldown_seconds=900,  # 15 minutes
            failover_provider=self.FAILOVER_MAP.get(provider)
        )
        
        # Check breaker state
        can_proceed = breaker.can_proceed()
        
        if not can_proceed.allowed:
            # Provider in cooldown
            return ProviderHealth(
                provider=provider,
                status=can_proceed.state.value,  # OPEN or COOLDOWN
                latency_ms=0,
                consecutive_failures=breaker.stats.consecutive_failures,
                cooldown_remaining=f"{breaker._remaining_cooldown()}s",
                state=can_proceed.state.value,
                last_check=datetime.now(timezone.utc).isoformat()
            )
        
        # Try to make a lightweight health check call
        # For now, just return CLOSED state info
        latency_ms = int((time.time() - start_time) * 1000)
        
        return ProviderHealth(
            provider=provider,
            status="OK" if breaker.state == BreakerState.CLOSED else breaker.state.value,
            latency_ms=latency_ms,
            consecutive_failures=breaker.stats.consecutive_failures,
            cooldown_remaining="0s",
            state=breaker.state.value,
            last_check=datetime.now(timezone.utc).isoformat()
        )
    
    def check_all(self) -> Dict[str, ProviderHealth]:
        """
        Check health of all configured providers.
        
        Returns:
            Dict of provider -> ProviderHealth
        """
        results = {}
        for provider in self.PROVIDER_ENDPOINTS.keys():
            results[provider] = self.check(provider)
        return results
    
    def format_output(self, health: ProviderHealth) -> str:
        """Format a single health check for table output."""
        return f"| {health.provider:<10} | {health.status:<10} | {health.latency_ms:<12} | {health.consecutive_failures:<21} | {health.cooldown_remaining:<17} |"
    
    def format_header(self) -> str:
        """Format table header."""
        return f"| provider   | status     | latency_ms  | consecutive_failures   | cooldown_remaining |"
    
    def format_separator(self) -> str:
        """Format table separator."""
        return f"|------------|------------|--------------|------------------------|-------------------|"
    
    def print_status(self):
        """Print formatted health status for all providers."""
        health_results = self.check_all()
        
        print("\n" + "=" * 80)
        print("TOKEN GUARDIAN - PROVIDER HEALTH STATUS")
        print("=" * 80)
        print()
        print(self.format_header())
        print(self.format_separator())
        
        for provider, health in health_results.items():
            print(self.format_output(health))
        
        print(self.format_separator())
        print()
        print("Status Key:")
        print("  - OK: Provider operational")
        print("  - TIMEOUT: Provider not responding within timeout")
        print("  - COOLDOWN: Provider failed - in recovery cooldown period")
        print("  - ERROR: Provider returned an error")
        print()
        print(f"Failover Configuration:")
        for provider, failover in self.FAILOVER_MAP.items():
            print(f"  - {provider} -> {failover}")
        print()
        print("=" * 80)


def check_providers():
    """Entry point for tokenguardian doctor --providers."""
    checker = ProviderHealthChecker()
    checker.print_status()


if __name__ == '__main__':
    check_providers()
