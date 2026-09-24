"""Sabre Developer Hub (Flight Shop API) Licensed GDS Adapter.

This adapter is part of the sanctioned replacement for the airline portals
that reject programmatic access at the transport level (Air India, IndiGo's
IP-range block, MakeMyTrip/Yatra TLS walls). Instead of fingerprint/IP-rotation
evasion tooling, it pulls licensed, ToS-compliant fare data from Sabre's own
Developer Hub -- Sabre is a major GDS distribution channel for Air India and
IndiGo inventory, so a single test-account credential can cover both blocked
carriers with genuine GDS fare/schedule data.

Data flow (no scraping happens anywhere):
    1. OAuth2 token   POST {base}/v2/auth/token
         Authorization: Basic base64(username:password)
         body: grant_type=client_credentials (& client_id/client_secret)
    2. Flight Shop    POST {base}/v1/offers/flightShop
         Authorization: Bearer <access_token>
         JSON body: SearchCriteria (Leg From/To/Date, PTC=ADT,
                    CabinPreferences=ECONOMY, CurrencyCode=INR)

Environments:
    cert (PLAY test)  https://api-crt.cert.havail.sabre.com
    prod              https://api.platform.sabre.com

Access: Dev Studio / Developer Hub registration is free and self-service
(create an app -> User ID + Password -> exchange for an OAuth token). This
remains live after Amadeus decommissioned its free self-service portal on
2026-07-17, so Sabre is the recommended self-service licensed GDS route for
hackathon use. Without credentials this adapter raises
``SabreCredentialsMissing`` internally, which the base class converts to the
tagged calibrated fallback -- behavior is unchanged for anyone who hasn't
configured a key, and any fallback stays honestly tagged
(``feed_type=PARTNER_API`` + ``extraction_method=CALIBRATED_MODEL``).

Schema-status note (important): the Flight Shop request here follows the
documented ``v1/offers/flightShop`` reference, but the *response* parser is
written defensively against the documented offer model (Offers -> Price /
Flights -> FlightNumber / Carrier / ScheduledDateTime) because no live
response payload was available at development time (no sandbox credential in
this environment). If the live response differs, the parser degrades
gracefully (empty result -> calibrated fallback, never fabricated REAL data);
reconcile ``parse_flight_shop`` against one real response once a credential
exists. The quote ``is_synthetic`` flag stays False ONLY for genuinely
extracted API data.
"""

import base64
import datetime
import logging
import os
import re
import time
import uuid
from typing import Any, Dict, List

import requests

from packages.shared.config import settings
from services.collectors.ota.base_ota_scraper import BaseOTAScraper

logger = logging.getLogger(__name__)

_BASE_URLS = {
    "cert": "https://api-crt.cert.havail.sabre.com",
    "prod": "https://api.platform.sabre.com",
}

# Module-level OAuth2 token cache, mirroring the Amadeus adapter: tokens are
# short-lived and shared across corridor queries, so one lookup per window.
_token_cache: Dict[str, Any] = {"access_token": None, "expires_at": 0.0}


class SabreCredentialsMissing(Exception):
    """Raised when SABRE_USERNAME/PASSWORD aren't configured.

    Caught by ``BaseOTAScraper.scrape_corridor``'s exception handling, which
    converts it to the calibrated fallback -- same pattern as
    ``RapidAPIKeyMissing`` in the Skyscanner adapter.
    """


def _dig(node: Any, *keys: str) -> Any:
    """Case-insensitive dict traversal over the primary key only.

    Sabre field casing varies between documentation generations; this helper
    walks candidate key spellings without deep merging, so a mismatched
    structure simply yields None and the caller can fall back or skip.
    """
    for key in keys:
        if isinstance(node, dict):
            for k, v in node.items():
                if str(k).lower() == key.lower():
                    return v
    return None


def _parse_iso8601_duration(duration: Any) -> int:
    """Parses either an ISO-8601 duration (``PT2H50M``) or a minute count."""
    if duration is None:
        return 0
    if isinstance(duration, (int, float)):
        return int(duration)
    text = str(duration).strip()
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?", text)
    if match:
        return int(match.group(1) or 0) * 60 + int(match.group(2) or 0)
    return 0


class SabreScraper(BaseOTAScraper):
    """GDS partner collector querying the Sabre Flight Shop API.

    Real-data path goes through Sabre's own REST API (see module docstring);
    the calibrated fallback is tagged so it can never be mistaken for a
    genuine market observation.
    """

    FEED_TYPE = "PARTNER_API"

    def __init__(self):
        super().__init__(
            source_id=14,
            source_name="Sabre Developer Hub",
            domain="developer.sabre.com",
            standard_convenience_fee=0.0,  # GDS totals are full out-of-pocket
        )

    # ------------------------------------------------------------------ auth
    def _base_url(self) -> str:
        env = (os.environ.get("SABRE_ENV") or settings.SABRE_ENV or "cert").lower()
        return _BASE_URLS.get(env, _BASE_URLS["cert"])

    def _credentials(self) -> tuple:
        username = os.environ.get("SABRE_USERNAME", "") or settings.SABRE_USERNAME
        password = os.environ.get("SABRE_PASSWORD", "") or settings.SABRE_PASSWORD
        if not username or not password:
            raise SabreCredentialsMissing(
                "SABRE_USERNAME / SABRE_PASSWORD not set -- register a free "
                "self-service account at https://developer.sabre.com (My Apps -> "
                "create app -> User ID + Password) to enable licensed GDS data. "
                "Without them the Sabre adapter degrades to the tagged calibrated "
                "fallback."
            )
        return username, password

    def _get_access_token(self) -> str:
        """Returns a cached, unexpired OAuth2 bearer token, fetching if needed."""
        if _token_cache["access_token"] and time.time() < _token_cache["expires_at"]:
            return _token_cache["access_token"]

        username, password = self._credentials()
        token_url = (
            os.environ.get("SABRE_TOKEN_URL")
            or settings.SABRE_TOKEN_URL
            or f"{self._base_url()}/v2/auth/token"
        )
        basic = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        resp = requests.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": username,
                "client_secret": password,
            },
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        # Modern OAuth2-style responses carry access_token; older Sabre
        # responses wrap the binary security token under TokenCreateRS.
        token = payload.get("access_token") or (
            (payload.get("TokenCreateRS") or {}).get("BinarySecurityToken")
        )
        if not token:
            raise ValueError("Sabre token response contained no access_token/BinarySecurityToken")
        expires_in = float(payload.get("expires_in") or 1800)
        _token_cache["access_token"] = token
        _token_cache["expires_at"] = time.time() + max(expires_in - 60.0, 60.0)
        return token

    def _auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._get_access_token()}", "Accept": "application/json"}

    # ------------------------------------------------------------- execution
    def _execute_scrape(
        self,
        origin_airport: str,
        destination_airport: str,
        travel_date: datetime.date,
        advance_days: int,
    ) -> List[Dict[str, Any]]:
        headers = self._auth_headers()  # raises SabreCredentialsMissing -> fallback

        shop_url = (
            os.environ.get("SABRE_SHOP_URL")
            or settings.SABRE_SHOP_URL
            or f"{self._base_url()}/v1/offers/flightShop"
        )
        body = {
            "SearchCriteria": {
                "Leg": [
                    {
                        "From": {"AirportCode": origin_airport},
                        "To": {"AirportCode": destination_airport},
                        "Date": travel_date.isoformat(),
                    }
                ],
                "PTC": ["ADT"],
                "CabinPreferences": [{"CabinType": "ECONOMY"}],
                "CurrencyCode": "INR",
            },
            "ClientContext": {"ClientToken": str(uuid.uuid4())},
        }
        resp = requests.post(shop_url, json=body, headers=headers, timeout=30)
        # One transparent retry on an expired/rotated token, then let the
        # base-class exception handling degrade to the tagged fallback.
        if resp.status_code == 401:
            _token_cache["access_token"] = None
            _token_cache["expires_at"] = 0.0
            resp = requests.post(
                shop_url, json=body, headers=self._auth_headers(), timeout=30
            )
        resp.raise_for_status()

        payload = resp.json()
        return self.parse_flight_shop(
            payload, origin_airport, destination_airport, travel_date, advance_days
        )

    # ---------------------------------------------------------------- parsing
    def parse_flight_shop(
        self,
        payload: Dict[str, Any],
        origin_airport: str,
        destination_airport: str,
        travel_date: datetime.date,
        advance_days: int,
    ) -> List[Dict[str, Any]]:
        """Normalizes a ``/v1/offers/flightShop`` response into quote dicts.

        Public so tests can verify schema conformance against a payload
        fixture without any network access. Defensive by design: unknown or
        changed response shapes yield fewer quotes, never fabricated data.

        SCHEMA-ASSUMPTION: the response is modeled on the documented offer
        shape -- ``Offers[]`` { ``Price``, ``Flights[]`` { ``FlightNumber``,
        ``Carrier``, ``Departure/Arrival {AirportCode, ScheduledDateTime}`` } }.
        Reconcile against one live sandbox response before relying on it.
        """
        offers = payload.get("Offers") or payload.get("offers") or []
        if not offers:
            # Some responses may nest under an "AirOffers"/"Itineraries" node.
            offers = payload.get("AirOffers") or payload.get("Itineraries") or []

        quotes: List[Dict[str, Any]] = []
        seen: set = set()

        for offer in offers:
            price_node = _dig(offer, "Price", "price")
            if not isinstance(price_node, dict):
                continue
            total_fare = _dig(price_node, "Amount", "raw", "TotalAmount")
            try:
                total_fare = float(total_fare or 0.0)
            except (TypeError, ValueError):
                continue
            base_fare = _dig(price_node, "BaseAmount", "BaseFare", "base")
            try:
                base_fare = float(base_fare) if base_fare is not None else total_fare
            except (TypeError, ValueError):
                base_fare = total_fare
            # PRD Section 62 valid-fare bounds -- a GDS quote outside these is
            # not a usable observation (e.g. zero-fare offer placeholders).
            if not (1500.0 <= total_fare <= 60000.0):
                continue

            # Flights / segments for this offer (first leg -> flights list, or
            # a single nested Itinerary node).
            flight_node = _dig(offer, "Flights", "flights", "FlightGroups")
            legs = flight_node if isinstance(flight_node, list) else None
            if not legs:
                itin = _dig(offer, "Itinerary", "itinerary")
                legs = _dig(itin, "Flights", "flights") if isinstance(itin, dict) else None
                legs = [legs] if isinstance(legs, dict) else (legs or [])
            if isinstance(legs, list) and legs and isinstance(legs[0], dict) and "Flights" in legs[0]:
                # FlightGroups shape: [{ "Flights": [...] }]
                grouped = []
                for group in legs:
                    grouped.extend(group.get("Flights") or [])
                legs = grouped
            if not legs:
                continue

            first = legs[0]
            last = legs[-1]
            carrier = _dig(first, "Carrier", "MarketingCarrier", "marketingCarrier") or {}
            carrier_code = (
                _dig(carrier, "AirlineCode", "DisplayCode", "CarrierCode")
                or _dig(first, "CarrierCode", "AirlineCode")
                or ""
            )
            number = str(_dig(first, "FlightNumber", "flightNumber", "Number") or "")
            carrier_code = str(carrier_code).strip().upper()
            number = number.strip().replace(" ", "").replace("-", "")
            # Some responses prefix the flight number with the carrier code
            # ("AI 806") -- drop the redundant prefix so it cannot double.
            if number[: len(carrier_code)].upper() == carrier_code:
                number = number[len(carrier_code):]
            if not carrier_code or not number:
                continue
            flight_identifier = f"{carrier_code}-{number}"

            departure_at = _dig(
                _dig(first, "Departure", "departure") or {}, "ScheduledDateTime", "DateTime", "at"
            ) or ""
            arrival_at = _dig(
                _dig(last, "Arrival", "arrival") or {}, "ScheduledDateTime", "DateTime", "at"
            ) or ""
            departure_time = str(departure_at)[11:16] or "00:00"
            arrival_time = str(arrival_at)[11:16] or None
            stops = int(
                _dig(first, "NumberOfStops", "stopCount") or (len(legs) - 1)
            )

            dedup_key = (flight_identifier, departure_time)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            seats = _dig(offer, "NumberOfBookableSeats", "SeatsRemaining", "Availability")
            is_sold_out = seats is not None and not isinstance(seats, dict) and int(seats) == 0

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
                    "departure_iso": str(departure_at),
                    "arrival_iso": str(arrival_at),
                    "duration_minutes": _parse_iso8601_duration(
                        _dig(first, "Duration", "duration", "DurationInMinutes", "durationInMinutes")
                    ),
                    "stopover_count": stops,
                    "inventory_status": "SOLD_OUT" if is_sold_out else "AVAILABLE",
                    "fare_breakdown": {
                        "base_fare": round(base_fare, 2),
                        "taxes_fees": round(max(total_fare - base_fare, 0.0), 2),
                        "total_payable": round(total_fare, 2),
                    },
                    # Repo-native quote schema
                    "origin_airport": origin_airport,
                    "destination_airport": destination_airport,
                    "travel_date": travel_date.isoformat(),
                    "departure_time": departure_time,
                    "arrival_time": arrival_time,
                    "advance_purchase_days": advance_days,
                    "stops": stops,
                    "base_fare": round(base_fare, 2),
                    "tax_amount": round(max(total_fare - base_fare, 0.0), 2),
                    "total_fare": round(total_fare, 2),
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
