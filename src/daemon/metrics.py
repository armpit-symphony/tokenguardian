#!/usr/bin/env python3
"""
Token Guardian Prometheus Metrics
Tracks tokens used, cost, requests, errors, and latency
"""
from prometheus_client import Counter, Histogram, Gauge, Info, REGISTRY, generate_latest
from functools import wraps
import time

# Tokens used counter - tracks total tokens by model
tokens_used = Counter(
    'tokenguardian_tokens_used_total',
    'Total number of tokens processed',
    ['model', 'provider']
)

# Cost counter - tracks total cost by model
cost_total = Counter(
    'tokenguardian_cost_total_dollars',
    'Total cost in USD',
    ['model', 'provider']
)

# Request counter
requests_total = Counter(
    'tokenguardian_requests_total',
    'Total number of requests',
    ['model', 'provider', 'status']
)

# Error counter
errors_total = Counter(
    'tokenguardian_errors_total',
    'Total number of errors',
    ['model', 'provider', 'error_type']
)

# Request latency histogram
request_latency = Histogram(
    'tokenguardian_request_latency_seconds',
    'Request latency in seconds',
    ['model', 'provider'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Active requests gauge
active_requests = Gauge(
    'tokenguardian_active_requests',
    'Number of active requests being processed',
    ['model', 'provider']
)

# Daemon uptime gauge
daemon_uptime_seconds = Gauge(
    'tokenguardian_daemon_uptime_seconds',
    'Daemon uptime in seconds'
)

# Shadow/live mode gauge
daemon_mode = Gauge(
    'tokenguardian_daemon_mode',
    'Daemon mode (1=live, 0=shadow)',
    ['mode']
)

# Cache hit ratio
cache_hits = Counter(
    'tokenguardian_cache_hits_total',
    'Total cache hits'
)

cache_misses = Counter(
    'tokenguardian_cache_misses_total',
    'Total cache misses'
)

# Info metric
daemon_info = Info(
    'tokenguardian_daemon',
    'Token Guardian daemon information'
)


def track_request(model: str, provider: str, status: str = 'success'):
    """Record a request"""
    requests_total.labels(model=model, provider=provider, status=status).inc()


def track_tokens(model: str, provider: str, count: int):
    """Record token usage"""
    tokens_used.labels(model=model, provider=provider).inc(count)


def track_cost(model: str, provider: str, cost: float):
    """Record cost in dollars"""
    cost_total.labels(model=model, provider=provider).inc(cost)


def track_error(model: str, provider: str, error_type: str):
    """Record an error"""
    errors_total.labels(model=model, provider=provider, error_type=error_type).inc()


def track_latency(model: str, provider: str, duration: float):
    """Record request latency"""
    request_latency.labels(model=model, provider=provider).observe(duration)


def track_cache_hit():
    """Record cache hit"""
    cache_hits.inc()


def track_cache_miss():
    """Record cache miss"""
    cache_misses.inc()


def latency_timer(model: str, provider: str):
    """Decorator to track latency of a function"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            active_requests.labels(model=model, provider=provider).inc()
            try:
                result = func(*args, **kwargs)
                track_request(model, provider, 'success')
                return result
            except Exception as e:
                track_request(model, provider, 'error')
                track_error(model, provider, type(e).__name__)
                raise
            finally:
                duration = time.time() - start_time
                track_latency(model, provider, duration)
                active_requests.labels(model=model, provider=provider).dec()
        return wrapper
    return decorator


def update_daemon_info(version: str = '1.0.0', mode: str = 'shadow'):
    """Update daemon info metric"""
    daemon_info.info({
        'version': version,
        'mode': mode
    })


def update_uptime(uptime_seconds: float):
    """Update daemon uptime"""
    daemon_uptime_seconds.set(uptime_seconds)


def update_mode(mode: str):
    """Update daemon mode"""
    daemon_mode.labels(mode=mode).set(1 if mode == 'live' else 0)


def get_metrics():
    """Generate Prometheus metrics output"""
    return generate_latest(REGISTRY)


def get_content_type():
    """Get content type for metrics response"""
    return 'text/plain'
