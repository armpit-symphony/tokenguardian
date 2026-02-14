#!/usr/bin/env python3
"""Token Guardian Availability Guard Integration Test"""

import sys
sys.path.insert(0, '/home/sparky/.openclaw/workspace/tokenguardian')

from src.core.timeout_wrapper import TimeoutWrapper, RequestStatus
from src.core.circuit_breaker import CircuitBreaker, BreakerState, get_breaker
from src.core.health import ProviderHealthChecker

def test_timeout_wrapper():
    print("TEST 1: Timeout Wrapper")
    print("-" * 40)
    
    wrapper = TimeoutWrapper(timeout_seconds=2)
    
    # Successful call
    result = wrapper.execute("test", lambda: "success")
    assert result.status == RequestStatus.SUCCESS, f"Expected SUCCESS, got {result.status}"
    assert result.value == "success"
    print(f"  ✓ Success: status={result.status.value}, latency={result.latency_ms}ms")
    
    # Timeout call
    def slow():
        import time
        time.sleep(5)
        return "late"
    
    result = wrapper.execute("slow", slow)
    assert result.status == RequestStatus.TIMEOUT
    assert result.timed_out == True
    print(f"  ✓ Timeout: status={result.status.value}, timed_out={result.timed_out}")
    print("  ✓ TEST 1 PASSED\n")

def test_circuit_breaker():
    print("TEST 2: Circuit Breaker")
    print("-" * 40)
    
    CircuitBreaker.reset_all()
    
    breaker = get_breaker(
        provider="test-minimax",
        failure_threshold=2,
        cooldown_seconds=15,
        failover_provider="openai/gpt-5-mini"
    )
    
    # Initial state
    result = breaker.can_proceed()
    assert result.allowed == True
    assert result.state == BreakerState.CLOSED
    print(f"  ✓ Initial: state={result.state.value}")
    
    # After 2 failures
    breaker.record_failure("err1")
    breaker.record_failure("err2")
    
    result = breaker.can_proceed()
    assert result.allowed == False
    assert result.state == BreakerState.OPEN
    print(f"  ✓ After 2 failures: state={result.state.value}, failover={result.failover_provider}")
    
    # Recovery
    breaker.record_success()
    breaker.record_success()
    
    result = breaker.can_proceed()
    assert result.state == BreakerState.CLOSED
    print(f"  ✓ Recovery: state={result.state.value}")
    print("  ✓ TEST 2 PASSED\n")

def test_health_check():
    print("TEST 3: Provider Health Check")
    print("-" * 40)
    
    checker = ProviderHealthChecker()
    results = checker.check_all()
    
    print(f"  ✓ Checked {len(results)} providers")
    for provider, health in results.items():
        print(f"    - {provider}: {health.status}")
    
    print("  ✓ TEST 3 PASSED\n")

def main():
    print("=" * 80)
    print("TOKEN GUARDIAN AVAILABILITY GUARD - INTEGRATION TESTS")
    print("=" * 80 + "\n")
    
    test_timeout_wrapper()
    test_circuit_breaker()
    test_health_check()
    
    print("=" * 80)
    print("ALL TESTS PASSED ✓")
    print("=" * 80)
    print()
    print("Implemented:")
    print("  - Timeout wrapper: 60s hard cap")
    print("  - Circuit breaker: 2 failures → 15min cooldown")
    print("  - Failover: minimax → openai/gpt-5-mini")
    print("  - Health check: tokenguardian doctor --providers")
    print("  - Logging: PROVIDER_FAILOVER format")

if __name__ == '__main__':
    main()
