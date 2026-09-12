"""Common Flight Entity Resolution & Matcher Engine.

Clusters quotes from Carrier Direct portals and disparate OTAs (MakeMyTrip, Ixigo,
EaseMyTrip, Yatra, Cleartrip, Skyscanner) into unified physical flight entities.
"""

import re
from typing import Any, Dict, List


class FlightEntityMatcher:
    """Matches and harmonizes flight quotes across heterogeneous travel platforms."""

    CARRIER_NAME_TO_CODE = {
        "INDIGO": "6E",
        "AIR INDIA": "AI",
        "SPICEJET": "SG",
        "AKASA": "QP",
        "AKASA AIR": "QP",
        "AIR INDIA EXPRESS": "IX",
    }

    @classmethod
    def normalize_flight_number(cls, raw_fno: str, carrier_code: str = "") -> str:
        """
        Normalizes variations like '6E-205', '6E 205', '6e205', 'IndiGo 205', '205'
        into canonical format '6E-205'. Correctly handles numeric IATA codes like 6E.
        """
        cleaned = str(raw_fno).strip().upper()

        carrier = carrier_code.upper().strip() if carrier_code else ""

        if not carrier:
            for name, code in cls.CARRIER_NAME_TO_CODE.items():
                if name in cleaned:
                    carrier = code
                    cleaned = cleaned.replace(name, "").strip()
                    break

        if cleaned.isdigit():
            num = cleaned
        elif "-" in cleaned:
            parts = cleaned.split("-", 1)
            if not carrier:
                carrier = parts[0].strip()
            num_match = re.search(r"(\d+)", parts[1])
            num = num_match.group(1) if num_match else "101"
        elif " " in cleaned:
            parts = cleaned.split(" ", 1)
            if not carrier:
                carrier = parts[0].strip()
            num_match = re.search(r"(\d+)", parts[1])
            num = num_match.group(1) if num_match else "101"
        elif carrier and cleaned.startswith(carrier):
            remainder = cleaned[len(carrier) :].strip(" -_")
            num_match = re.search(r"(\d+)", remainder)
            num = num_match.group(1) if num_match else "101"
        else:
            alpha_match = re.match(r"^([A-Z0-9]{2})(\d+)$", cleaned)
            if alpha_match:
                if not carrier:
                    carrier = alpha_match.group(1)
                num = alpha_match.group(2)
            else:
                num_match = re.search(r"(\d+)", cleaned)
                num = num_match.group(1) if num_match else "101"

        if not carrier:
            carrier = "6E"

        return f"{carrier}-{num}"

    @classmethod
    def cluster_common_flights(
        cls,
        quotes: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Groups quotes from all sources into common flight clusters.
        Key: (canonical_flight_number, travel_date)
        """
        clusters: Dict[str, Dict[str, Any]] = {}

        for q in quotes:
            carrier = q.get("carrier_code", "6E").upper()
            raw_fno = q.get("flight_number", "")
            canonical_fno = cls.normalize_flight_number(raw_fno, carrier)

            travel_date = str(q.get("travel_date", ""))[:10]
            dep_time = str(q.get("departure_time", "08:00"))[:5]
            arr_time = str(q.get("arrival_time", "10:15"))[:5]

            cluster_key = f"{canonical_fno}_{travel_date}"

            if cluster_key not in clusters:
                carrier_names = {
                    "6E": "IndiGo",
                    "AI": "Air India",
                    "SG": "SpiceJet",
                    "QP": "Akasa Air",
                    "IX": "Air India Express",
                }
                clusters[cluster_key] = {
                    "cluster_key": cluster_key,
                    "flight_number": canonical_fno,
                    "carrier_code": carrier,
                    "carrier_name": carrier_names.get(carrier, carrier),
                    "origin_airport": q.get("origin_airport", "DEL"),
                    "destination_airport": q.get("destination_airport", "BOM"),
                    "travel_date": travel_date,
                    "departure_time": dep_time,
                    "arrival_time": arr_time,
                    "quotes_by_source": {},
                    "all_quotes": [],
                }

            source_name = q.get("source_name", "Unknown Source")
            clusters[cluster_key]["quotes_by_source"][source_name] = q
            clusters[cluster_key]["all_quotes"].append(q)

        return clusters
