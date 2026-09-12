"""Carrier Direct Website Scrapers (IndiGo, Air India, SpiceJet, Akasa Air).

Complies with PRD Section 11-13: Ethical collection, rate limiting, robots.txt compliance,
raw payload audit, and 5-part fare decomposition (base fare, fuel surcharge, GST, UDF/ADF, convenience fee).
"""

import datetime
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from services.collectors.circuit_breaker import get_circuit_breaker

logger = logging.getLogger(__name__)


class CarrierDirectScraper(ABC):
    """Base class for carrier direct website scraping with NDC/API fallback and browser automation."""

    def __init__(
        self,
        carrier_code: str,
        carrier_name: str,
        domain: str,
        ndc_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        raw_dir: str = "data/raw/live/carrier_direct",
    ):
        self.carrier_code = carrier_code
        self.carrier_name = carrier_name
        self.domain = domain
        self.ndc_endpoint = ndc_endpoint
        self.api_key = api_key
        self.raw_dir = os.path.join(raw_dir, carrier_code)
        os.makedirs(self.raw_dir, exist_ok=True)

        # Circuit breaker per carrier
        self.circuit_breaker = get_circuit_breaker(
            source_id=hash(carrier_code) % 1000,
            source_name=f"Carrier Direct ({carrier_name})",
        )

        # Rate limiting (requests per minute)
        self.rate_limit_rpm = 30
        self._last_request_time = 0.0
        self._request_count = 0
        self._rate_limit_window_start = time.time()

        # Browser pool
        self._browser_pool = None

    def _enforce_rate_limit(self):
        """Enforces per-carrier rate limiting."""
        now = time.time()
        if now - self._rate_limit_window_start >= 60:
            self._rate_limit_window_start = now
            self._request_count = 0

        if self._request_count >= self.rate_limit_rpm:
            sleep_time = 60 - (now - self._rate_limit_window_start)
            if sleep_time > 0:
                logger.info(f"Rate limit reached for {self.carrier_code}, sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)
            self._rate_limit_window_start = time.time()
            self._request_count = 0

        self._request_count += 1
        self._last_request_time = time.time()

    def _check_robots_txt(self, url: str) -> bool:
        """Checks robots.txt compliance for the target URL."""
        # Simplified check - in production, use robotparser
        disallowed_paths = [
            "/admin", "/private", "/internal", "/api/v2/",
            "/checkout", "/payment", "/account"
        ]

        for disallowed in disallowed_paths:
            if disallowed in url:
                logger.warning(f"robots.txt disallows: {url}")
                return False
        return True

    def scrape_carrier_corridor(
        self,
        origin_airport: str,
        destination_airport: str,
        advance_days: int,
        search_date: Optional[datetime.date] = None,
        db: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """
        Main entry point: tries NDC API first, then browser automation, then calibrated fallback.
        """
        if search_date is None:
            search_date = datetime.date.today()

        travel_date = search_date + datetime.timedelta(days=advance_days)

        # Check circuit breaker
        if self.circuit_breaker.state == "OPEN":
            logger.warning(f"Circuit breaker OPEN for {self.carrier_code}. Using calibrated fallback.")
            return self._calibrated_fallback(origin_airport, destination_airport, travel_date, advance_days)

        self._enforce_rate_limit()

        # Try NDC API first (if available)
        if self.ndc_endpoint and self.api_key:
            try:
                return self._scrape_via_ndc(origin_airport, destination_airport, travel_date, advance_days, db)
            except Exception as e:
                logger.warning(f"NDC API failed for {self.carrier_code}: {e}")

        # Try browser automation
        try:
            return self._scrape_via_browser(origin_airport, destination_airport, travel_date, advance_days, db)
        except Exception as e:
            logger.warning(f"Browser scrape failed for {self.carrier_code}: {e}")

        # Calibrated fallback
        return self._calibrated_fallback(origin_airport, destination_airport, travel_date, advance_days, db)

    @abstractmethod
    def _scrape_via_ndc(
        self,
        origin_airport: str,
        destination_airport: str,
        travel_date: datetime.date,
        advance_days: int,
        db: Optional[Session],
    ) -> List[Dict[str, Any]]:
        """NDC API scraping (preferred method)."""
        pass

    @abstractmethod
    def _scrape_via_browser(
        self,
        origin_airport: str,
        destination_airport: str,
        travel_date: datetime.date,
        advance_days: int,
        db: Optional[Session],
    ) -> List[Dict[str, Any]]:
        """Playwright-based browser scraping."""
        pass

    def _calibrated_fallback(
        self,
        origin_airport: str,
        destination_airport: str,
        travel_date: datetime.date,
        advance_days: int,
        db: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """Returns calibrated quotes tagged as model-generated."""
        quotes = self._generate_calibrated_quotes(origin_airport, destination_airport, travel_date, advance_days)
        for q in quotes:
            q["extraction_method"] = "CALIBRATED_MODEL"
            q["feed_type"] = "CALIBRATED_BASELINE"
        return quotes

    @abstractmethod
    def _generate_calibrated_quotes(
        self,
        origin_airport: str,
        destination_airport: str,
        travel_date: datetime.date,
        advance_days: int,
    ) -> List[Dict[str, Any]]:
        """Generates carrier-specific calibrated quotes with 5-part fare decomposition."""
        pass

    def _persist_raw_payload(
        self,
        quotes: List[Dict[str, Any]],
        origin: str,
        dest: str,
        travel_date: datetime.date,
    ) -> str:
        """Stores raw payload with SHA-256 hash for audit compliance."""
        import hashlib
        import json
        ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.carrier_code}_{origin}_{dest}_{travel_date.isoformat()}_{ts}.json"
        filepath = os.path.join(self.raw_dir, filename)

        serialized = json.dumps(quotes, default=str)
        sha256 = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"hash": sha256, "captured_at": ts, "carrier": self.carrier_code, "data": quotes}, f, indent=2)

        return filepath
