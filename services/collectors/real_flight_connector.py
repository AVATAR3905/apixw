"""Real Flight Search Connector using Google Flights RPC (PRD Section 24, 25).

Functions as:
1. Pricing Validator: Cross-checks carrier direct prices for markups, discounts, and parity.
2. Resilient Fallback: Automatically provides live quotes if a carrier portal is down or rate-limited.
"""

import datetime
import hashlib
import json
import os
from typing import Any, Dict, List, Optional

from fast_flights import FlightQuery, Passengers, create_query, get_flights
from sqlalchemy.orm import Session

from packages.schemas.models import RawPayload, Source
from services.collectors.circuit_breaker import (
    CircuitBreaker,
    CollectorErrorCode,
    CollectorException,
)
from services.collectors.drift_detector import FareSchemaDriftDetector, record_drift
from services.collectors.response_cache import get_fare_cache


class RealFlightRPCConnector:
    """Queries live flight quotes via Google Flights RPC endpoints."""

    SOURCE_NAME = "Google Flights RPC Validator & Fallback"

    def __init__(self, raw_dir: str = "data/raw/live/rpc"):
        self.raw_dir = raw_dir
        os.makedirs(raw_dir, exist_ok=True)
        self.circuit_breaker = CircuitBreaker(
            source_id=6,
            source_name=self.SOURCE_NAME,
            failure_threshold=5,
            recovery_timeout_seconds=60.0,
        )

    def search_corridor_horizon(
        self,
        origin_airport: str,
        destination_airport: str,
        advance_days: int,
        search_date: Optional[datetime.date] = None,
        db: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """
        Queries live flight offers for a city pair and horizon.
        Returns normalized raw flight quotes.
        """
        if search_date is None:
            search_date = datetime.date.today()

        travel_date = search_date + datetime.timedelta(days=advance_days)
        travel_date_str = travel_date.isoformat()

        def _fetch():
            query = create_query(
                flights=[
                    FlightQuery(
                        date=travel_date_str,
                        from_airport=origin_airport.upper(),
                        to_airport=destination_airport.upper(),
                    )
                ],
                seat="economy",
                trip="one-way",
                passengers=Passengers(adults=1),
                currency="INR",
            )
            return get_flights(query)

        cache_key = f"rpc:{origin_airport.upper()}:{destination_airport.upper()}:{travel_date_str}"
        cache = get_fare_cache()
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            results = self.circuit_breaker.call(_fetch, db=db)
        except Exception as e:
            raise CollectorException(
                CollectorErrorCode.SOURCE_UNAVAILABLE,
                f"Google Flights RPC query failed for {origin_airport}->{destination_airport}: {e}",
            )

        quotes = []
        raw_items = []

        for r in results:
            if not r.flights:
                continue

            first_leg = r.flights[0]
            airline_name = r.airlines[0] if r.airlines else "Unknown"

            # Map airline name to IATA code
            carrier_code = self._map_carrier_name_to_code(airline_name)

            flight_no = f"{carrier_code}-{getattr(first_leg, 'flight_number', '101')}"
            if not flight_no or "None" in flight_no:
                plane_str = getattr(first_leg, "plane_type", "A320") or "A320"
                flight_no = f"{carrier_code}-{abs(hash(airline_name + plane_str)) % 899 + 100}"

            dep_dt = getattr(first_leg, "departure", None)
            dep_time_str = (
                f"{dep_dt.time[0]:02d}:{dep_dt.time[1]:02d}"
                if dep_dt and hasattr(dep_dt, "time")
                else "08:00"
            )

            quote_data = {
                "source": "RPC_VALIDATOR_FALLBACK",
                "origin_airport": origin_airport.upper(),
                "destination_airport": destination_airport.upper(),
                "travel_date": travel_date_str,
                "advance_purchase_days": advance_days,
                "carrier_code": carrier_code,
                "carrier_name": airline_name,
                "flight_number": flight_no,
                "departure_time": dep_time_str,
                "stops": len(r.flights) - 1,
                "total_fare": float(r.price),
                "cabin_class": "ECONOMY",
                "fare_family": "BASIC",
                "extraction_method": "RPC",
            }
            quotes.append(quote_data)
            raw_items.append(quote_data)

        # Schema-drift alarm: fail loudly if the RPC record shape rotated.
        report = FareSchemaDriftDetector.detect(quotes)
        record_drift(report)
        FareSchemaDriftDetector.raise_if_drifting(report)

        if quotes:
            cache.set(cache_key, quotes)

        # Persist raw payload with SHA-256 hash
        self._store_raw_payload(db, raw_items, origin_airport, destination_airport, travel_date_str)
        return quotes

    def _map_carrier_name_to_code(self, name: str) -> str:
        name_lower = name.lower()
        if "indigo" in name_lower:
            return "6E"
        elif "air india express" in name_lower:
            return "IX"
        elif "air india" in name_lower:
            return "AI"
        elif "spicejet" in name_lower:
            return "SG"
        elif "akasa" in name_lower:
            return "QP"
        elif "vistara" in name_lower:
            return "AI"  # Integrated into Air India
        return "6E"

    def _store_raw_payload(
        self,
        db: Optional[Session],
        data: List[Dict[str, Any]],
        origin: str,
        dest: str,
        date_str: str,
    ):
        raw_json = json.dumps(data, sort_keys=True)
        payload_hash = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
        filename = f"rpc_{origin}_{dest}_{date_str}_{payload_hash[:10]}.json"
        filepath = os.path.join(self.raw_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(raw_json)

        if db:
            src = db.query(Source).filter(Source.name == self.SOURCE_NAME).first()
            if src:
                rp = RawPayload(
                    source_id=src.id,
                    payload_uri=filepath,
                    payload_hash=payload_hash,
                    content_type="application/json",
                    captured_at=datetime.datetime.now(datetime.UTC),
                )
                db.add(rp)
                db.commit()
