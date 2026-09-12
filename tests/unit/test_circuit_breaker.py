"""Unit tests for Circuit Breaker and bounded retry policy."""

import pytest

from services.collectors.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CollectorErrorCode,
    CollectorException,
)


def test_circuit_breaker_tripping_after_failures():
    """Circuit breaker trips to OPEN after 5 consecutive failures and blocks subsequent calls."""
    breaker = CircuitBreaker(
        source_id=99,
        source_name="Failing API",
        failure_threshold=5,
        max_retries=1,  # 1 try per call
        initial_backoff_seconds=0.001,
    )

    def failing_func():
        raise CollectorException(CollectorErrorCode.TIMEOUT, "Gateway timeout")

    # Trigger 4 failures -> state should remain CLOSED
    for _ in range(4):
        with pytest.raises(CollectorException):
            breaker.call(failing_func)
        assert breaker.state == "CLOSED"

    # 5th failure trips breaker
    with pytest.raises(CollectorException):
        breaker.call(failing_func)
    assert breaker.state == "OPEN"

    # 6th call is immediately rejected without calling function
    with pytest.raises(CircuitBreakerOpenError):
        breaker.call(failing_func)


def test_circuit_breaker_resets_on_success():
    """Successful calls reset consecutive failure counters."""
    breaker = CircuitBreaker(
        source_id=100, source_name="Reliable API", failure_threshold=5, max_retries=1
    )

    def flaky_func(counter=[0]):
        counter[0] += 1
        if counter[0] == 1:
            raise CollectorException(CollectorErrorCode.TIMEOUT, "Temporary glitch")
        return "SUCCESS"

    # 1 failure
    with pytest.raises(CollectorException):
        breaker.call(flaky_func)
    assert breaker.consecutive_failures == 1

    # 1 success resets failure count
    res = breaker.call(flaky_func)
    assert res == "SUCCESS"
    assert breaker.consecutive_failures == 0
    assert breaker.state == "CLOSED"
