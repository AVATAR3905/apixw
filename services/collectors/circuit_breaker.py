"""Circuit breaker, bounded retry policy, and error taxonomy for collector jobs (PRD Section 54 & 63)."""

import enum
import time
from typing import Any, Callable, Dict, Optional

from sqlalchemy.orm import Session

from packages.schemas.models import Source


class CollectorErrorCode(str, enum.Enum):
    """Standardized error codes for collector failures."""

    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    TIMEOUT = "TIMEOUT"
    PARSER_ERROR = "PARSER_ERROR"
    SCHEMA_CHANGED = "SCHEMA_CHANGED"
    NO_RESULTS = "NO_RESULTS"
    DATABASE_ERROR = "DATABASE_ERROR"
    UNKNOWN = "UNKNOWN"


class CollectorException(Exception):
    """Base exception for collector operations with standardized error code."""

    def __init__(self, code: CollectorErrorCode, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class CircuitBreakerOpenError(CollectorException):
    """Raised when request is rejected because circuit breaker is OPEN."""

    def __init__(self, source_name: str):
        super().__init__(
            CollectorErrorCode.SOURCE_UNAVAILABLE,
            f"Circuit breaker is OPEN for source '{source_name}'. Requests temporarily suspended.",
        )


class CircuitBreaker:
    """
    Per-source circuit breaker and retry manager.
    - CLOSED: Normal operation. Failures increment failure counter.
    - OPEN: Tripped after failure_threshold consecutive errors. Blocks requests.
    - HALF_OPEN: Tests recovery after recovery_timeout_seconds.
    """

    def __init__(
        self,
        source_id: int,
        source_name: str,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 60.0,
        max_retries: int = 3,
        initial_backoff_seconds: float = 0.05,
    ):
        self.source_id = source_id
        self.source_name = source_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.max_retries = max_retries
        self.initial_backoff_seconds = initial_backoff_seconds

        self.consecutive_failures = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.last_failure_time: Optional[float] = None
        self.last_success_time: Optional[float] = None

    def call(self, func: Callable[..., Any], db: Optional[Session] = None, *args, **kwargs) -> Any:
        """Executes the collector function wrapped in circuit breaker and bounded retry policy."""
        now = time.time()

        # Check circuit state
        if self.state == "OPEN":
            if self.last_failure_time and (
                now - self.last_failure_time >= self.recovery_timeout_seconds
            ):
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpenError(self.source_name)

        attempt = 0
        last_exception = None

        while attempt < self.max_retries:
            attempt += 1
            try:
                result = func(*args, **kwargs)
                self._record_success(db)
                return result
            except CollectorException as e:
                last_exception = e
                # Do not retry fatal permission denial or schema changes
                if e.code in (
                    CollectorErrorCode.PERMISSION_DENIED,
                    CollectorErrorCode.SCHEMA_CHANGED,
                ):
                    self._record_failure(db)
                    raise e
            except Exception as e:
                last_exception = CollectorException(CollectorErrorCode.UNKNOWN, str(e))

            # Exponential backoff before next attempt
            if attempt < self.max_retries:
                backoff = self.initial_backoff_seconds * (2 ** (attempt - 1))
                time.sleep(backoff)

        # All retries exhausted
        self._record_failure(db)
        if last_exception:
            raise last_exception
        raise CollectorException(
            CollectorErrorCode.UNKNOWN, "Retries exhausted without specific exception"
        )

    def _record_success(self, db: Optional[Session] = None):
        """Records a successful operation, resetting failure counter."""
        self.consecutive_failures = 0
        self.state = "CLOSED"
        self.last_success_time = time.time()

        if db:
            src = db.query(Source).filter(Source.id == self.source_id).first()
            if src and src.health_status == "DEGRADED":
                src.health_status = "ACTIVE"
                db.commit()

    def _record_failure(self, db: Optional[Session] = None):
        """Records a failed operation. Trips circuit to OPEN if threshold reached."""
        self.consecutive_failures += 1
        self.last_failure_time = time.time()

        if self.consecutive_failures >= self.failure_threshold:
            self.state = "OPEN"
            if db:
                src = db.query(Source).filter(Source.id == self.source_id).first()
                if src and src.health_status not in ("DISABLED", "DOWN"):
                    src.health_status = "DEGRADED"
                    db.commit()


# Global registry of circuit breakers per source
_breakers: Dict[int, CircuitBreaker] = {}


def get_circuit_breaker(source_id: int, source_name: str) -> CircuitBreaker:
    """Retrieves or creates a circuit breaker instance for a given source."""
    if source_id not in _breakers:
        _breakers[source_id] = CircuitBreaker(source_id=source_id, source_name=source_name)
    return _breakers[source_id]
