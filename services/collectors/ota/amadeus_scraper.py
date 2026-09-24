"""Amadeus Enterprise API (Flight Offers Search) Licensed GDS Adapter.

This adapter is the sanctioned replacement for the airline portals that block
programmatic access at the TLS/HTTP2 level (Air India, and IndiGo's IP-range
block). Instead of building fingerprint/IP-rotation evasion tooling, it pulls
licensed, ToS-compliant fare data from Amadeus' own API -- Air India and
IndiGo are both Amadeus-distributed inventory, so a single partner key covers
both blocked carriers with genuine GDS fare/schedule data.

Data flow (no scraping happens anywhere):
    1. OAuth2 client-credentials token  POST {base}/v1/security/oauth2/token
    2. Flight Offers Search             GET  {base}/v2/shopping/flight-offers
       ?originLocationCode=DEL&destinationLocationCode=MAA
       &departureDate=YYYY-MM-DD&adults=1&currencyCode=INR

Access status (important -- changed 2026): Amadeus retired its free
self-service developer portal on **July 17, 2026**; all self-service API keys
were disabled and developers.amadeus.com now fronts the Amadeus Enterprise API
Portal only. The REST contract used here (OAuth2 client-credentials +
/v2/shopping/flight-offers) is identical on the Enterprise portal, but
credentials require a commercial agreement. For self-service hackathon access,
prefer the Sabre test environment (``ota/sabre_scraper.py``) or the RapidAPI
"Sky Scrapper" wrapper (``ota/skyscanner_scraper.py``).

This adapter is retained code-ready: set AMADEUS_CLIENT_ID / AMADEUS_CLIENT_SECRET
(plus AMADEUS_ENV=test|production) when an Enterprise credential is available.
Without credentials it raises ``AmadeusCredentialsMissing`` internally, which
the base class's existing exception handling converts to the calibrated
fallback -- behavior is unchanged for anyone who hasn't configured a key, and
any fallback stays honestly tagged (``feed_type=PARTNER_API`` +
``extraction_method=CALIBRATED_MODEL``).

The Enterprise sandbox/test environment returns real GDS fares/schedules for
constrained dates; the quote ``is_synthetic`` flag stays False ONLY for
genuinely extracted API data.
"""

import datetime
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

import requests

from packages.shared.config import settings
from services.collectors.ota.base_ota_scraper import BaseOTAScraper

logger = logging.getLogger(__name__)

_BASE_URLS = {
    "test": "https://test.api.amadeus.com",
    "production": "https://api.amadeus.com",
}

# Module-level OAuth2 token cache. Access tokens are short-lived (~30 min) and
# shared across corridor queries, so one lookup per expiry window is enough.
_token_cache: Dict[str, Any] = {"access_token": None, "expires_at": 0.0}


class AmadeusCredentialsMissing(Exception):
    """Raised when AMADEUS_CLIENT_ID/SECRET aren't configured.

    Caught by ``BaseOTAScraper.scrape_corridor``'s exception handling, which
    converts it to the calibrated fallback -- same pattern as
    ``RapidAPIKeyMissing`` in the Skyscanner adapter.
    """


def _parse_iso8601_duration(duration: Optional[str]) -> int:
    """Parses an ISO-8601 duration (``PT2H05M``) into total minutes."""
    if not duration:
        return 0
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?", duration.strip())
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    return hours * 60 + minutes


class AmadeusScraper(BaseOTAScraper):
    """GDS partner collector querying Amadeus Flight Offers Search.

    Real-data path goes through Amadeus' own REST API (see module docstring);
    the calibrated fallback is tagged so it can never be mistaken for a
    genuine market observation.
    """

    FEED_TYPE = "PARTNER_API"

    def __init__(self):
        super().__init__(
            source_id=13,
            source_name="Amadeus Self-Service API",
            domain="api.amadeus.com",
            standard_convenience_fee=0.0,  # GDS totals are full out-of-pocket
        )

    # ------------------------------------------------------------------ auth
    def _base_url(self) -> str:
        override = os.environ.get("AMADEUS_BASE_URL") or settings.AMADEUS_BASE_URL
        if override:
            return override.rstrip("/")
        env = (os.environ.get("AMADEUS_ENV") or settings.AMADEUS_ENV or "test").lower()
        return _BASE_URLS.get(env, _BASE_URLS["test"])

    def _credentials(self) -> tuple:
        client_id = os.environ.get("AMADEUS_CLIENT_ID", "") or settings.AMADEUS_CLIENT_ID
        client_secret = (
            os.environ.get("AMADEUS_CLIENT_SECRET", "") or settings.AMADEUS_CLIENT_SECRET
        )
        if not client_id or not client_secret:
            raise AmadeusCredentialsMissing(
                "AMADEUS_CLIENT_ID / AMADEUS_CLIENT_SECRET not set. NOTE: Amadeus "
                "decommissioned its self-service developer portal on 2026-07-17 -- "
                "free keys are no longer issued; credentials must come from the "
                "Amadeus Enterprise API Portal (commercial agreement). For "
                "self-service licensed fare data, use the Sabre test environment "
                "(SABRE_USERNAME/SABRE_PASSWORD) or RapidAPI Sky Scrapper "
                "(RAPIDAPI_KEY) instead."
            )
        return client_id, client_secret

    def _get_access_token(self) -> str:
        """Returns a cached, unexpired OAuth2 bearer token, fetching if needed."""
        if _token_cache["access_token"] and time.time() < _token_cache["expires_at"]:
            return _token_cache["access_token"]

        client_id, client_secret = self._credentials()
        resp = requests.post(
            f"{self._base_url()}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        token = payload["access_token"]
        # Refresh ~60s before the server-side expiry to avoid mid-run 401 races.
        expires_in = int(payload.get("expires_in", 1800))
        _token_cache["access_token"] = token
        _token_cache["expires_at"] = time.time() + max(expires_in - 60, 60)
        return token

    def _auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._get_access_token()}"}

    # ------------------------------------------------------------- execution
    def _execute_scrape(
        self,
        origin_airport: str,
        destination_airport: str,
        travel_date: datetime.date,
        advance_days: int,
    ) -> List[Dict[str, Any]]:
        headers = self._auth_headers()  # raises AmadeusCredentialsMissing -> fallback

        resp = requests.get(
            f"{self._base_url()}/v2/shopping/flight-offers",
            params={
                "originLocationCode": origin_airport,
                "destinationLocationCode": destination_airport,
                "departureDate": travel_date.isoformat(),
                "adults": 1,
                "currencyCode": "INR",
                "max": 30,
            },
            headers=headers,
            timeout=20,
        )
        # One transparent retry on an expired/rotated token, then let the
        # base-class exception handling degrade to the tagged fallback.
        if resp.status_code == 401:
            _token_cache["access_token"] = None
            _token_cache["expires_at"] = 0.0
            resp = requests.get(
                f"{self._base_url()}/v2/shopping/flight-offers",
                params={
                    "originLocationCode": origin_airport,
                    "destinationLocationCode": destination_airport,
                    "departureDate": travel_date.isoformat(),
                    "adults": 1,
                    "currencyCode": "INR",
                    "max": 30,
                },
                headers=self._auth_headers(),
                timeout=20,
            )
        resp.raise_for_status()

        payload = resp.json()
        return self.parse_flight_offers(
            payload, origin_airport, destination_airport, travel_date, advance_days
        )

    # ---------------------------------------------------------------- parsing
    def parse_flight_offers(
        self,
        payload: Dict[str, Any],
        origin_airport: str,
        destination_airport: str,
        travel_date: datetime.date,
        advance_days: int,
    ) -> List[Dict[str, Any]]:
        """Normalizes a ``/v2/shopping/flight-offers`` response into quote dicts.

        Public so tests can verify schema conformance against a payload
        fixture without any network access.
        """
        offers = payload.get("data") or []
        quotes: List[Dict[str, Any]] = []
        seen: set = set()

        for offer in offers:
            itineraries = offer.get("itineraries") or []
            if not itineraries:
                continue
            segments = itineraries[0].get("segments") or []
            if not segments:
                continue

            first = segments[0]
            last = segments[-1]
            carrier_code = (first.get("carrierCode") or "").strip().upper()
            number = str(first.get("number", "")).strip()
            if not carrier_code or not number:
                continue
            flight_identifier = f"{carrier_code}-{number}"

            departure_at = (first.get("departure") or {}).get("at") or ""
            arrival_at = (last.get("arrival") or {}).get("at") or ""
            departure_time = departure_at[11:16] or "00:00"
            arrival_time = arrival_at[11:16] or None
            stops = sum(int(seg.get("numberOfStops", 0) or 0) for seg in segments)

            price = offer.get("price") or {}
            try:
                base_fare = round(float(price.get("base", 0.0) or 0.0), 2)
                total_fare = round(
                    float(price.get("total") or price.get("grandTotal") or 0.0), 2
                )
            except (TypeError, ValueError):
                continue
            # PRD Section 62 valid-fare bounds -- a GDS quote outside these is
            # not a usable observation (e.g. zero-fare offer placeholders).
            if not (1500.0 <= total_fare <= 60000.0):
                continue

            dedup_key = (flight_identifier, departure_time)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            seats = offer.get("numberOfBookableSeats")
            is_sold_out = seats is not None and int(seats) == 0

            quotes.append(
                {
                    "source_id": self.source_id,
                    "source_name": self.source_name,
                    "source_domain": self.domain,
                    "carrier_code": carrier_code,
                    "flight_number": flight_identifier,
                    # SIH 26056 uniform schema aliases (superset of repo fields)
                    "provider_id": self.source_name,
                    "flight_identifier": flight_identifier,
                    "departure_iso": departure_at,
                    "arrival_iso": arrival_at,
                    "duration_minutes": _parse_iso8601_duration(
                        itineraries[0].get("duration")
                    ),
                    "stopover_count": stops,
                    "inventory_status": "SOLD_OUT" if is_sold_out else "AVAILABLE",
                    "fare_breakdown": {
                        "base_fare": base_fare,
                        "taxes_fees": round(max(total_fare - base_fare, 0.0), 2),
                        "total_payable": total_fare,
                    },
                    # Repo-native quote schema
                    "origin_airport": origin_airport,
                    "destination_airport": destination_airport,
                    "travel_date": travel_date.isoformat(),
                    "departure_time": departure_time,
                    "arrival_time": arrival_time,
                    "advance_purchase_days": advance_days,
                    "stops": stops,
                    "base_fare": base_fare,
                    "tax_amount": round(max(total_fare - base_fare, 0.0), 2),
                    "total_fare": total_fare,
                    "cabin_class": "ECONOMY",
                    "fare_family": "BASIC",
                    "is_unconditional": True,
                    "is_sold_out": is_sold_out,
                    "extraction_method": "NETWORK_API",
                }
            )
        return quotes

    # ------------------------------------------------- calibrated fallback
    def _generate_calibrated_quotes(
        self,
        origin_airport: str,
        destination_airport: str,
        travel_date: datetime.date,
        advance_days: int,
    ) -> List[Dict[str, Any]]:
        """Deterministic market-calibrated model quotes (never REAL-tagged)."""
        corridor = f"{origin_airport}-{destination_airport}"
        base_tariffs = {
            "DEL-BOM": 3000.0,
            "DEL-BLR": 3500.0,
            "BOM-BLR": 2800.0,
            "DEL-CCU": 3400.0,
            "DEL-HYD": 3200.0,
            "BOM-MAA": 3100.0,
            "BLR-HYD": 2600.0,
            "DEL-MAA": 3600.0,
            "DEL-IXS": 5200.0,
            "DEL-DHM": 4800.0,
        }
        corridor_base = base_tariffs.get(corridor, 3200.0)
        h_mult = {1: 2.04, 7: 1.45, 14: 1.00, 30: 0.94, 45: 0.88}.get(advance_days, 1.0)
        route_price = corridor_base * h_mult

        # Generic 2-3h trunk-corridor schedule mixing the two target carriers.
        flights_schedule = [
            {"carrier": "6E", "fno": "6E-205", "dep": "06:15", "arr": "08:45", "mod": 1.00},
            {"carrier": "AI", "fno": "AI-806", "dep": "09:30", "arr": "12:00", "mod": 1.15},
            {"carrier": "6E", "fno": "6E-532", "dep": "13:00", "arr": "15:30", "mod": 1.05},
            {"carrier": "AI", "fno": "AI-814", "dep": "18:15", "arr": "20:45", "mod": 1.20},
            {"carrier": "6E", "fno": "6E-701", "dep": "21:00", "arr": "23:30", "mod": 0.95},
        ]

        quotes = []
        for fl in flights_schedule:
            base = round(route_price * fl["mod"], 2)
            fuel = round(base * 0.18, 2)
            udf = 350.0
            gst = round(base * 0.05, 2)
            total = round(base + fuel + udf + gst, 2)

            quotes.append(
                {
                    "source_id": self.source_id,
                    "source_name": self.source_name,
                    "source_domain": self.domain,
                    "carrier_code": fl["carrier"],
                    "flight_number": fl["fno"],
                    "flight_identifier": fl["fno"],
                    "provider_id": self.source_name,
                    "departure_iso": f"{travel_date.isoformat()}T{fl['dep']}:00",
                    "arrival_iso": f"{travel_date.isoformat()}T{fl['arr']}:00",
                    "duration_minutes": 150,
                    "stopover_count": 0,
                    "inventory_status": "AVAILABLE",
                    "fare_breakdown": {
                        "base_fare": base,
                        "taxes_fees": round(fuel + udf + gst, 2),
                        "total_payable": total,
                    },
                    "origin_airport": origin_airport,
                    "destination_airport": destination_airport,
                    "travel_date": travel_date.isoformat(),
                    "departure_time": fl["dep"],
                    "arrival_time": fl["arr"],
                    "advance_purchase_days": advance_days,
                    "stops": 0,
                    "base_fare": base,
                    "fuel_surcharge": fuel,
                    "udf_adf": udf,
                    "gst_taxes": gst,
                    "convenience_fee": 0.0,
                    "promotional_discount": 0.0,
                    "total_fare": total,
                    "cabin_class": "ECONOMY",
                    "fare_family": "BASIC",
                    "is_unconditional": True,
                    "is_sold_out": False,
                }
            )
        return quotes
