"""Abstract Base Scraper for Online Travel Aggregators (OTAs) & Metasearch Engines.

Complies with PRD Section 11, 12, 13 (Ethical collection, rate limiting, and raw payload audit).
"""

import datetime
import hashlib
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from services.collectors.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class BaseOTAScraper(ABC):
    """Base class for all OTA and metasearch flight price collectors."""

    def __init__(
        self,
        source_id: int,
        source_name: str,
        domain: str,
        standard_convenience_fee: float = 350.0,
        raw_dir: str = "data/raw/live/ota",
    ):
        self.source_id = source_id
        self.source_name = source_name
        self.domain = domain
        self.standard_convenience_fee = standard_convenience_fee
        self.raw_dir = os.path.join(raw_dir, domain.replace(".", "_"))
        os.makedirs(self.raw_dir, exist_ok=True)

        self.circuit_breaker = CircuitBreaker(
            source_id=self.source_id,
            source_name=self.source_name,
            failure_threshold=5,
            recovery_timeout_seconds=60.0,
        )

    def scrape_corridor(
        self,
        origin_airport: str,
        destination_airport: str,
        travel_date: datetime.date,
        advance_days: int,
        db: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """
        Public entrypoint. Checks circuit breaker, tries live collection,
        falls back to calibrated realistic simulation if blocked or offline.
        """
        if self.circuit_breaker.state == "OPEN":
            logger.warning(f"Circuit breaker tripped for {self.source_name}. Bypassing.")
            return []

        try:
            quotes = self._execute_scrape(
                origin_airport=origin_airport.upper(),
                destination_airport=destination_airport.upper(),
                travel_date=travel_date,
                advance_days=advance_days,
            )
            if quotes:
                for q in quotes:
                    q["extraction_method"] = q.get("extraction_method", "NETWORK_XHR")
                self.circuit_breaker._record_success(db)
                self._persist_raw_payload(quotes, origin_airport, destination_airport, travel_date)
                return quotes
            else:
                self.circuit_breaker._record_failure(db)
                return self._calibrated_fallback(
                    origin_airport=origin_airport,
                    destination_airport=destination_airport,
                    travel_date=travel_date,
                    advance_days=advance_days,
                )
        except Exception as e:
            logger.error(f"Scraper error on {self.source_name}: {e}")
            self.circuit_breaker._record_failure(db)
            return self._calibrated_fallback(
                origin_airport=origin_airport,
                destination_airport=destination_airport,
                travel_date=travel_date,
                advance_days=advance_days,
            )

    def _calibrated_fallback(
        self,
        origin_airport: str,
        destination_airport: str,
        travel_date: datetime.date,
        advance_days: int,
    ) -> List[Dict[str, Any]]:
        """Returns calibrated simulation quotes clearly tagged as model-generated (not scraped)."""
        quotes = self._generate_calibrated_quotes(
            origin_airport=origin_airport,
            destination_airport=destination_airport,
            travel_date=travel_date,
            advance_days=advance_days,
        )
        for q in quotes:
            q["extraction_method"] = q.get("extraction_method", "CALIBRATED_MODEL")
        return quotes

    @abstractmethod
    def _execute_scrape(
        self,
        origin_airport: str,
        destination_airport: str,
        travel_date: datetime.date,
        advance_days: int,
    ) -> List[Dict[str, Any]]:
        """Platform-specific scraping logic (Playwright intercept or API query)."""
        pass

    @abstractmethod
    def _generate_calibrated_quotes(
        self,
        origin_airport: str,
        destination_airport: str,
        travel_date: datetime.date,
        advance_days: int,
    ) -> List[Dict[str, Any]]:
        """Generates realistic market quotes reflecting platform-specific fee and discount behaviors."""
        pass

    def _persist_raw_payload(
        self,
        quotes: List[Dict[str, Any]],
        origin: str,
        dest: str,
        travel_date: datetime.date,
    ) -> str:
        """Stores raw payload with SHA-256 hash for audit compliance."""
        ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{origin}_{dest}_{travel_date.isoformat()}_{ts}.json"
        filepath = os.path.join(self.raw_dir, filename)

        serialized = json.dumps(quotes, default=str)
        sha256 = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"hash": sha256, "captured_at": ts, "data": quotes}, f, indent=2)

        return filepath
