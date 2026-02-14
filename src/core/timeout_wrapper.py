"""
Token Guardian Timeout Wrapper
Work Order: #TG-MINIMAX-AVAILABILITY-GUARD

Provides a 60-second timeout wrapper for provider API calls.
Does NOT modify OpenClaw internals - wraps at Token Guardian layer.
"""

import signal
from typing import Callable, Any, Optional
from dataclasses import dataclass
from enum import Enum


class TimeoutError(Exception):
    """Raised when a request exceeds the timeout threshold."""
    pass


class RequestStatus(Enum):
    SUCCESS = "SUCCESS"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


@dataclass
class RequestResult:
    """Result of a wrapped API request."""
    status: RequestStatus
    value: Any = None
    error: Optional[str] = None
    latency_ms: int = 0
    timed_out: bool = False


class TimeoutWrapper:
    """
    Wraps API calls with a configurable timeout.
    
    Usage:
        wrapper = TimeoutWrapper(timeout_seconds=60)
        result = wrapper.execute(provider_name, api_call_function)
        
        if result.status == RequestStatus.TIMEOUT:
            # Handle timeout - trigger circuit breaker
    """
    
    DEFAULT_TIMEOUT_SECONDS = 60
    
    def __init__(self, timeout_seconds: int = None):
        self.timeout_seconds = timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS
    
    def execute(
        self, 
        provider: str, 
        api_call: Callable[[], Any]
    ) -> RequestResult:
        """
        Execute an API call with timeout protection.
        
        Args:
            provider: Provider name (for logging)
            api_call: Function to execute
            
        Returns:
            RequestResult with status, value, error, and latency
        """
        import time
        start_time = time.time()
        
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Request to {provider} timed out after {self.timeout_seconds}s")
        
        # Set up timeout signal (Unix only)
        # On Windows, use threading approach instead
        old_handler = None
        if hasattr(signal, 'SIGALRM'):
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(self.timeout_seconds)
        
        try:
            value = api_call()
            latency_ms = int((time.time() - start_time) * 1000)
            
            return RequestResult(
                status=RequestStatus.SUCCESS,
                value=value,
                latency_ms=latency_ms
            )
            
        except TimeoutError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return RequestResult(
                status=RequestStatus.TIMEOUT,
                error=str(e),
                latency_ms=latency_ms,
                timed_out=True
            )
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return RequestResult(
                status=RequestStatus.ERROR,
                error=str(e),
                latency_ms=latency_ms
            )
            
        finally:
            # Clean up timeout
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)


def wrap_request(
    provider: str,
    api_call: Callable[[], Any],
    timeout_seconds: int = 60
) -> RequestResult:
    """
    Convenience function to wrap a single request.
    
    Args:
        provider: Provider name
        api_call: Function to execute
        timeout_seconds: Timeout in seconds (default 60)
    
    Returns:
        RequestResult
    """
    wrapper = TimeoutWrapper(timeout_seconds)
    return wrapper.execute(provider, api_call)
