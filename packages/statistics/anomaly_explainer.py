"""Explainable anomaly alerts (APIX-2.2 Governance Intelligence).

Completes the anomaly detection loop: every detected anomaly is correlated against
the `atf_prices` fuel series, the festival / peak-demand calendar, carrier
availability data (SOLD_OUT pressure), and day-of-week patterns, then rendered as a
plain-English explanation suitable for a government statistician:

``DEL-BOM fares spiked 21.4% on 2026-10-17 — consistent with Diwali demand surge
(matched calendar window 2026-10-17) and tight availability (3 carriers SOLD_OUT).``
"""

import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from packages.schemas.models import ATFPrice, FareObservation
from packages.statistics.anomaly_service import PriceAnomalyService
from services.reference.festival_calendar import FestivalCalendarService

SOLD_OUT_RATIO_THRESHOLD = 0.10
ATF_MOVE_THRESHOLD_PCT = 1.0
FESTIVAL_PROXIMITY_DAYS = 3


class AnomalyExplainer:
    """Builds explainable alerts by correlating anomalies with context series."""

    @classmethod
    def get_alert_feed(
        cls,
        db: Session,
        days: int = 30,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Return the most recent anomaly events each paired with an explanation."""
        events = PriceAnomalyService.get_recent(db, days=days, limit=limit)
        alerts = []
        for e in events:
            try:
                obs_date = datetime.date.fromisoformat(e["observation_date"])
            except (TypeError, ValueError):
                obs_date = datetime.date.today()
            explanation = cls.explain(db, obs_date, series=e.get("series", "BASE_FARE"))
            alerts.append({**e, "explanation": explanation})

        return {
            "total_alerts": len(alerts),
            "unexplained_count": sum(
                1 for a in alerts if not a["explanation"].get("matched_signals")
            ),
            "alerts": alerts,
            "methodology_disclosure": cls._disclosure(),
        }

    @classmethod
    def explain(
        cls,
        db: Session,
        observation_date: datetime.date,
        series: str = "BASE_FARE",
        route_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a structured, plain-English explanation for an anomaly date."""
        atf_ctx = cls._atf_context(db, observation_date)
        calendar = cls._calendar_context(db, observation_date)
        avail = cls._availability_context(db, observation_date, route_code)
        dow = observation_date.strftime("%A")

        matched_signals = []
        parts = []

        if calendar["matched_event"]:
            matched_signals.append("calendar")
            parts.append(
                f"consistent with {calendar['event_label']} "
                f"(matched calendar window {calendar['matched_date']})"
            )
        if avail["sold_out_pressure"]:
            matched_signals.append("availability")
            parts.append(
                f"availability tightening — {avail['sold_out_ratio_pct']:.0f}% "
                f"of quotes SOLD_OUT across {avail['distinct_carriers_sold_out']} carrier(s)"
            )
        if atf_ctx["move_pct"] >= ATF_MOVE_THRESHOLD_PCT:
            matched_signals.append("atf")
            parts.append(f"ATF (Delhi) moved {atf_ctx['move_pct']:+.1f}% over the window")

        if not matched_signals:
            parts.append("no calendar/ATF/availability correlation found in observed data")

        subject = route_code or "national index"
        plain_text = (
            f"{subject} moved abnormally on {observation_date} ({dow}) — "
            + "; ".join(parts)
            + "."
        )

        return {
            "observation_date": observation_date.isoformat(),
            "day_of_week": dow,
            "matched_signals": matched_signals,
            "atf_prime_move_pct": round(atf_ctx["move_pct"], 2),
            "atf_prime_price": atf_ctx["latest_price"],
            "calendar": {
                "matched_event": calendar["matched_event"],
                "matched_date": calendar["matched_date"],
                "event_label": calendar["event_label"],
            },
            "availability": {
                "sold_out_ratio_pct": round(avail["sold_out_ratio_pct"], 2),
                "sold_out_quotes": avail["sold_out_quotes"],
                "total_quotes": avail["total_quotes"],
                "distinct_carriers_sold_out": avail["distinct_carriers_sold_out"],
            },
            "plain_text": plain_text,
        }

    @staticmethod
    def _festival_label_for(date: datetime.date) -> str:
        labels = {
            8: "Independence Day long-weekend",
            10: "Dussehra travel cluster",
            11: "Diwali festive peak",
            12: "Christmas / New Year window",
        }
        return labels.get(date.month, "peak-demand calendar event")

    @classmethod
    def _calendar_context(cls, db: Session, date: datetime.date) -> Dict[str, Any]:
        peaks = FestivalCalendarService.peak_date_set(db)
        for d in sorted(peaks):
            if abs((d - date).days) <= FESTIVAL_PROXIMITY_DAYS:
                return {
                    "matched_event": True,
                    "matched_date": d.isoformat(),
                    "event_label": cls._festival_label_for(d),
                }
        return {"matched_event": False, "matched_date": None, "event_label": None}

    @classmethod
    def _atf_context(cls, db: Session, date: datetime.date) -> Dict[str, Any]:
        window_start = date - datetime.timedelta(days=30)
        rows = (
            db.query(ATFPrice)
            .filter(
                ATFPrice.location == "Delhi",
                ATFPrice.date <= date,
                ATFPrice.date >= window_start,
            )
            .order_by(ATFPrice.date.asc())
            .all()
        )
        if len(rows) < 2:
            return {"latest_price": None, "move_pct": 0.0}
        first, last = rows[0].price_per_kl, rows[-1].price_per_kl
        move = (last - first) / first * 100.0 if first else 0.0
        return {"latest_price": last, "move_pct": move}

    @classmethod
    def _availability_context(
        cls, db: Session, date: datetime.date, route_code: Optional[str]
    ) -> Dict[str, Any]:
        query = db.query(FareObservation).filter(
            FareObservation.search_timestamp
            >= datetime.datetime.combine(date, datetime.time.min),
            FareObservation.search_timestamp
            <= datetime.datetime.combine(date, datetime.time.max),
        )
        if route_code:
            from packages.schemas.models import Route

            route = db.query(Route).filter(Route.route_code == route_code).first()
            if route:
                query = query.filter(FareObservation.route_id == route.id)

        rows = query.all()
        if not rows:
            return {
                "sold_out_ratio_pct": 0.0,
                "sold_out_quotes": 0,
                "total_quotes": 0,
                "distinct_carriers_sold_out": 0,
                "sold_out_pressure": False,
            }
        total = len(rows)
        sold_out = [r for r in rows if r.availability_status == "SOLD_OUT"]
        ratio = len(sold_out) / total
        carriers = {r.airline_id for r in sold_out}
        return {
            "sold_out_ratio_pct": ratio * 100.0,
            "sold_out_quotes": len(sold_out),
            "total_quotes": total,
            "distinct_carriers_sold_out": len(carriers),
            "sold_out_pressure": ratio >= SOLD_OUT_RATIO_THRESHOLD and len(carriers) >= 1,
        }

    @staticmethod
    def _disclosure() -> str:
        return (
            "Explanations are generated from stored observatory context (ATF prices, festival "
            "calendar, availability status) and are correlational, not causal."
        )
