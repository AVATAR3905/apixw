"""Mock Connector for pipeline testing and integration verification."""

import datetime
from typing import Any, Dict

from services.collectors.base import BaseConnector


class MockConnector(BaseConnector):
    """Test connector producing controlled payloads for testing."""

    def __init__(
        self, source_id: int = 1, source_name: str = "Mock Connector", should_fail: bool = False
    ):
        super().__init__(source_id=source_id, source_name=source_name)
        self.should_fail = should_fail

    def health_check(self) -> bool:
        return not self.should_fail

    def fetch_route_horizon(
        self, route_code: str, search_date: datetime.date, advance_days: int
    ) -> Dict[str, Any]:
        if self.should_fail:
            from services.collectors.circuit_breaker import CollectorErrorCode, CollectorException

            raise CollectorException(
                CollectorErrorCode.SOURCE_UNAVAILABLE, "Simulated mock source outage"
            )

        origin, dest = route_code.split("-")
        return {
            "status": "OK",
            "source": self.source_name,
            "route": route_code,
            "advance_days": advance_days,
            "fares": [
                {
                    "carrier": "6E",
                    "flight_number": "6E-501",
                    "cabin_class": "ECONOMY",
                    "fare_family": "BASIC",
                    "availability_status": "AVAILABLE",
                    "base_fare": 4200.0,
                    "fuel_surcharge": 850.0,
                    "tax_amount": 252.5,
                    "development_fee": 350.0,
                    "convenience_fee": 299.0,
                    "total_fare": 5951.5,
                    "is_carrier_min_fare": True,
                },
                {
                    "carrier": "AI",
                    "flight_number": "AI-602",
                    "cabin_class": "ECONOMY",
                    "fare_family": "BASIC",
                    "availability_status": "AVAILABLE",
                    "base_fare": 4500.0,
                    "fuel_surcharge": 850.0,
                    "tax_amount": 267.5,
                    "development_fee": 350.0,
                    "convenience_fee": 299.0,
                    "total_fare": 6266.5,
                    "is_carrier_min_fare": True,
                },
            ],
        }
