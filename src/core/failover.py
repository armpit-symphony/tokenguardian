"""
Token Guardian Failover Override
Work Order: #TG-MINIMAX-AVAILABILITY-GUARD

Provides automatic failover when a provider is in cooldown.
Routes requests to configured fallback provider during outages.
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone

from .circuit_breaker import CircuitBreaker, BreakerState


@dataclass
class FailoverResult:
    """Result of a failover check."""
    original_provider: str
    actual_provider: str
    failover_triggered: bool
    reason: Optional[str] = None
    cooldown_remaining: Optional[str] = None


class FailoverManager:
    """
    Manages provider failover during outages.
    
    Usage:
        failover = FailoverManager()
        
        # Check if failover needed
        result = failover.check("minimax", "openai/gpt-5-mini")
        if result.failover_triggered:
            # Route to result.actual_provider instead
            provider = result.actual_provider
    """
    
    # Default failover mappings
    DEFAULT_FAILOVER = {
        'minimax': 'openai/gpt-5-mini',
        'openai': 'anthropic/claude-3-5-sonnet',
        'xai': 'openai/gpt-5-mini',
        'anthropic': 'openai/gpt-5-mini'
    }
    
    def __init__(self, failover_map: Dict[str, str] = None):
        self.failover_map = failover_map or self.DEFAULT_FAILOVER.copy()
    
    def check(
        self, 
        provider: str, 
        default_fallback: str = None
    ) -> FailoverResult:
        """
        Check if failover should be triggered for a provider.
        
        Args:
            provider: Requested provider
            default_fallback: Default fallback if provider not in map
            
        Returns:
            FailoverResult with actual provider to use
        """
        # Get the configured fallback
        fallback = self.failover_map.get(provider, default_fallback)
        
        # Get circuit breaker state
        breaker = CircuitBreaker.get_breaker(
            provider=provider,
            failure_threshold=2,
            cooldown_seconds=900,  # 15 minutes
            failover_provider=fallback
        )
        
        can_proceed = breaker.can_proceed()
        
        if can_proceed.allowed:
            # Normal operation - no failover
            return FailoverResult(
                original_provider=provider,
                actual_provider=provider,
                failover_triggered=False
            )
        
        # Provider in cooldown - trigger failover
        return FailoverResult(
            original_provider=provider,
            actual_provider=fallback or can_proceed.failover_provider,
            failover_triggered=True,
            reason=can_proceed.reason,
            cooldown_remaining=f"{breaker._remaining_cooldown()}s"
        )
    
    def get_fallback(self, provider: str) -> Optional[str]:
        """Get configured fallback for a provider."""
        return self.failover_map.get(provider)
    
    def log_failover(self, result: FailoverResult):
        """Log a failover event."""
        log_entry = (
            f"PROVIDER_FAILOVER: from={result.original_provider} "
            f"to={result.actual_provider} "
            f"reason={result.reason or 'COOLDOWN'}"
        )
        print(f"[FAILOVER] {log_entry}")
        return log_entry
    
    def get_status(self) -> Dict[str, Any]:
        """Get failover manager status."""
        breakers = CircuitBreaker.all_breakers()
        
        status = {
            'failover_map': self.failover_map,
            'providers': {}
        }
        
        for provider, breaker in breakers.items():
            result = self.check(provider)
            status['providers'][provider] = {
                'original': result.original_provider,
                'actual': result.actual_provider,
                'failover_triggered': result.failover_triggered,
                'reason': result.reason,
                'cooldown_remaining': result.cooldown_remaining,
                'state': breaker.state.value,
                'consecutive_failures': breaker.stats.consecutive_failures
            }
        
        return status


# Singleton instance
_failover_manager: Optional[FailoverManager] = None


def get_failover_manager() -> FailoverManager:
    """Get the global failover manager instance."""
    global _failover_manager
    if _failover_manager is None:
        _failover_manager = FailoverManager()
    return _failover_manager


def should_failover(provider: str, default_fallback: str = None) -> FailoverResult:
    """
    Convenience function to check if failover is needed.
    
    Args:
        provider: Requested provider
        default_fallback: Default fallback if not configured
        
    Returns:
        FailoverResult
    """
    manager = get_failover_manager()
    return manager.check(provider, default_fallback)
