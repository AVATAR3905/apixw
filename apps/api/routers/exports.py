"""Researcher Data Export Router (Official Data Governance Standards)."""

import csv
import datetime
import io
import json

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from database.session import get_db
from packages.schemas.models import FareObservation, IndexValue, Route, RouteWeight

router = APIRouter(prefix="/api/v1/export", tags=["Researcher Data Exports"])


@router.get("/daily-index.csv")
def export_daily_index_csv(
    series: str = Query("BASE_FARE", pattern="^(BASE_FARE|TOTAL_PRICE)$"),
    horizon: int = Query(15),
    db: Session = Depends(get_db),
):
    """Exports daily headline or sub-index time series in CSV format."""
    query = db.query(IndexValue).filter(
        IndexValue.index_series == series,
        IndexValue.route_id.is_(None),
    )
    if horizon in (14, 15):
        query = query.filter(IndexValue.index_type.in_(["HEADLINE_T15", "HEADLINE_T14"]))
    else:
        query = query.filter(IndexValue.index_type == f"SUB_T{horizon}")

    records = query.order_by(IndexValue.period_start.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "date",
            "index_series",
            "index_type",
            "lead_time_days",
            "index_value",
            "daily_change_pct",
            "weekly_change_pct",
            "monthly_change_pct",
            "coverage_rate_pct",
            "is_low_coverage",
            "methodology_version",
        ]
    )

    for r in records:
        writer.writerow(
            [
                r.period_start.isoformat(),
                r.index_series,
                r.index_type,
                r.lead_time_days,
                r.index_value,
                r.daily_change_pct or "",
                r.weekly_change_pct or "",
                r.monthly_change_pct or "",
                r.coverage_rate,
                r.is_low_coverage,
                r.methodology_version,
            ]
        )

    output.seek(0)
    filename = f"airfare_index_{series.lower()}_t{horizon}_{datetime.date.today().isoformat()}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/daily-index.json")
def export_daily_index_json(
    series: str = Query("BASE_FARE", pattern="^(BASE_FARE|TOTAL_PRICE)$"),
    horizon: int = Query(15),
    db: Session = Depends(get_db),
):
    """Exports daily headline or sub-index time series in structured JSON format."""
    query = db.query(IndexValue).filter(
        IndexValue.index_series == series,
        IndexValue.route_id.is_(None),
    )
    if horizon in (14, 15):
        query = query.filter(IndexValue.index_type.in_(["HEADLINE_T15", "HEADLINE_T14"]))
    else:
        query = query.filter(IndexValue.index_type == f"SUB_T{horizon}")

    records = query.order_by(IndexValue.period_start.asc()).all()

    data = [
        {
            "date": r.period_start.isoformat(),
            "index_series": r.index_series,
            "index_type": r.index_type,
            "lead_time_days": r.lead_time_days,
            "index_value": r.index_value,
            "daily_change_pct": r.daily_change_pct,
            "weekly_change_pct": r.weekly_change_pct,
            "monthly_change_pct": r.monthly_change_pct,
            "coverage_rate": r.coverage_rate,
            "is_low_coverage": r.is_low_coverage,
            "methodology_version": r.methodology_version,
        }
        for r in records
    ]

    filename = f"airfare_index_{series.lower()}_t{horizon}_{datetime.date.today().isoformat()}.json"
    return Response(
        content=json.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/basket-weights.csv")
def export_basket_weights_csv(db: Session = Depends(get_db)):
    """Exports active DGCA route weights basket in CSV format."""
    records = (
        db.query(RouteWeight, Route)
        .join(Route, RouteWeight.route_id == Route.id)
        .filter(RouteWeight.effective_to.is_(None))
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "route_code",
            "origin_airport",
            "destination_airport",
            "corridor_type",
            "passenger_volume",
            "normalized_weight",
            "weight_pct",
            "methodology_version",
            "source_report",
        ]
    )

    for rw, r in records:
        writer.writerow(
            [
                r.route_code,
                r.origin_airport,
                r.destination_airport,
                r.corridor_type,
                rw.passenger_volume,
                rw.weight,
                round(rw.weight * 100, 2),
                rw.methodology_version,
                rw.source,
            ]
        )

    output.seek(0)
    filename = f"dgca_basket_weights_{datetime.date.today().isoformat()}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/route-observations.csv")
def export_route_observations_csv(
    route_code: str = Query("DEL-BOM"),
    limit: int = Query(500, le=5000),
    db: Session = Depends(get_db),
):
    """Exports raw fare observations for a given corridor in CSV format."""
    route = db.query(Route).filter(Route.route_code == route_code.upper()).first()
    if not route:
        return Response(content="Route not found", status_code=404)

    obs = (
        db.query(FareObservation)
        .filter(FareObservation.route_id == route.id)
        .order_by(FareObservation.search_timestamp.desc())
        .limit(limit)
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "search_timestamp",
            "travel_date",
            "advance_days",
            "flight_number",
            "cabin_class",
            "fare_family",
            "availability_status",
            "base_fare",
            "fuel_surcharge",
            "tax_amount",
            "development_fee",
            "convenience_fee",
            "total_fare",
            "quality_score",
            "quality_status",
        ]
    )

    for o in obs:
        writer.writerow(
            [
                o.search_timestamp.isoformat(),
                o.travel_date.isoformat(),
                o.advance_purchase_days,
                o.flight_number,
                o.cabin_class,
                o.fare_family,
                o.availability_status,
                o.base_fare,
                o.fuel_surcharge,
                o.tax_amount,
                o.development_fee,
                o.convenience_fee,
                o.total_fare,
                o.quality_score,
                o.quality_status,
            ]
        )

    output.seek(0)
    filename = f"observations_{route_code.lower()}_{datetime.date.today().isoformat()}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
