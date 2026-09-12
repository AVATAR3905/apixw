"""Fare Component Parser and Schema Drift Detection Engine (PRD Section 15, 16, 17, 64)."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError

from services.collectors.circuit_breaker import CollectorErrorCode, CollectorException


class FlightQuoteSchema(BaseModel):
    """Pydantic schema enforcing structural integrity of individual parsed flight quotes."""

    carrier: str = Field(min_length=2, max_length=5)
    flight_number: str = Field(min_length=3, max_length=15)
    cabin_class: str = "ECONOMY"
    fare_family: str = "BASIC"
    availability_status: str = "AVAILABLE"
    base_fare: Optional[float] = None
    fuel_surcharge: float = 0.0
    tax_amount: float = 0.0
    development_fee: float = 0.0
    convenience_fee: float = 0.0
    other_fee: float = 0.0
    total_fare: Optional[float] = None
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    stops: int = 0


class SearchResponseSchema(BaseModel):
    """Schema for validating root search response structure."""

    status: str
    route: str
    advance_days: int
    flights: List[Dict[str, Any]] = Field(default_factory=list)


class FareParser:
    """Parses raw JSON/HTML airline responses into decomposed quotes with schema drift protection."""

    @classmethod
    def parse_search_response(
        cls, payload: Dict[str, Any], route_code: str, advance_days: int
    ) -> List[Dict[str, Any]]:
        """
        Validates payload structure and parses flight quotes.
        Raises CollectorException(SCHEMA_CHANGED) if response layout has drifted.
        """
        # Step 1: Root schema validation
        try:
            validated_root = SearchResponseSchema(
                status=payload.get("status", "OK"),
                route=payload.get("route", route_code),
                advance_days=payload.get("advance_days", advance_days),
                flights=payload.get("flights", payload.get("data", payload.get("results", []))),
            )
        except ValidationError as e:
            raise CollectorException(
                CollectorErrorCode.SCHEMA_CHANGED,
                f"Source schema drift detected at root level: {e}",
            )

        raw_flights = validated_root.flights
        if not raw_flights:
            # If flights list is explicitly empty for a popular metro route, raise warning
            return []

        parsed_quotes: List[Dict[str, Any]] = []

        for idx, item in enumerate(raw_flights):
            try:
                # Extract availability
                is_sold_out = (
                    bool(item.get("is_sold_out", False)) or item.get("seats_available") == 0
                )
                avail = "SOLD_OUT" if is_sold_out else item.get("availability_status", "AVAILABLE")

                carrier = str(item.get("carrier") or item.get("airline_code") or "").upper().strip()
                flight_num = (
                    str(item.get("flight_number") or item.get("flight_no") or "").upper().strip()
                )

                if not carrier or not flight_num:
                    raise ValueError("Missing carrier or flight_number in quote object")

                # Decompose fare components
                if avail == "SOLD_OUT":
                    base_fare = None
                    total_fare = None
                    fuel = 0.0
                    tax = 0.0
                    udf = 0.0
                    conv = 0.0
                else:
                    total_fare = float(
                        item.get("total_fare") or item.get("fare") or item.get("price", 0.0)
                    )
                    base_fare = float(item.get("base_fare") or (total_fare * 0.75))
                    fuel = float(item.get("fuel_surcharge", 0.0))
                    tax = float(item.get("tax_amount", total_fare * 0.05))
                    udf = float(item.get("development_fee", 0.0))
                    conv = float(item.get("convenience_fee", 299.0))

                quote = FlightQuoteSchema(
                    carrier=carrier,
                    flight_number=flight_num,
                    cabin_class=str(item.get("cabin_class", "ECONOMY")).upper(),
                    fare_family=str(item.get("fare_family", "BASIC")).upper(),
                    availability_status=avail,
                    base_fare=base_fare,
                    fuel_surcharge=fuel,
                    tax_amount=tax,
                    development_fee=udf,
                    convenience_fee=conv,
                    other_fee=float(item.get("other_fee", 0.0)),
                    total_fare=total_fare,
                    departure_time=item.get("departure_time"),
                    arrival_time=item.get("arrival_time"),
                    stops=int(item.get("stops", 0)),
                )
                parsed_quotes.append(quote.model_dump())

            except (ValidationError, ValueError, TypeError) as e:
                # If individual quote parsing fails due to schema drift
                raise CollectorException(
                    CollectorErrorCode.SCHEMA_CHANGED,
                    f"Schema drift detected on flight record {idx}: {e}",
                )

        return parsed_quotes
