"""Daily Airfare Index Calculation Service (PRD Section 27, 28, 40.8, 41).

Implements industry-standard methodologies:
- Skytra: 28-day moving average, index divisor for continuity, waterfall data quality
- FAX: Weighted data source prioritization, outlier detection, quality flags
- BLS/CPI: Spot window for consistent trip definition, fixed specifications
- IMF/ABS: Jevons geometric mean for elementary indices, chain linking
"""
import datetime
from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy.orm import Session

from packages.schemas.models import FareObservation, IndexValue, Route, RouteWeight
from packages.shared.config import settings
from packages.shared.time_utils import utcnow
from packages.statistics.core_filter import CoreIndexFilter
from packages.statistics.estimators import RepresentativePriceEstimator
from packages.statistics.index_engine import AirfareIndexEngine
from packages.statistics.variance import IndexVarianceError, IndexVarianceEstimator
from packages.statistics.weights import DGCAWeightEngine


class DailyIndexCalculatorService:
    """Calculates daily headline index (T+15), unpooled horizon sub-indices, and route-level indices."""

    HORIZONS = [1, 7, 15, 30, 45]
    HEADLINE_HORIZON = 15
    PRICE_SERIES = ["BASE_FARE", "TOTAL_PRICE"]

    # Quality thresholds (Skytra/FAX inspired)
    MIN_ROUTES_FOR_LIVE = 8  # Min 8 of 10 routes for LIVE status
    MIN_CARRIERS_PER_ROUTE = 2  # Min 2 carriers per route
    MIN_COVERAGE_FOR_BETA = 80.0  # Min 80% coverage for BETA
    MIN_COVERAGE_FOR_LIVE = 90.0  # Min 90% coverage for LIVE
    MOVING_AVG_WINDOW = 28  # 28-day moving average (Skytra)
    SPOT_WINDOW_DAYS = 28  # Spot window for consistent pricing (BLS)

    @classmethod
    def get_route_representative_prices(
        cls,
        db: Session,
        observation_date: datetime.date,
        advance_days: int,
        price_field: str = "base_fare",
        series_type: str = "HEADLINE",
        require_continuity: bool = True,
    ) -> Dict[str, float]:
        """Calculates representative prices for all active routes on a date and horizon.

        Thin facade over :meth:`_route_estimates_for_series`, keeping exactly one
        source of truth for observation loading, CORE gating and the JEVONS
        estimator. Callers that only need prices never duplicate the estimator
        pass that variance / quality diagnostics require.
        """
        estimates = cls._route_estimates_for_series(
            db,
            observation_date,
            advance_days=advance_days,
            price_field=price_field,
            series_type=series_type,
            require_continuity=require_continuity,
        )
        return {rcode: est["representative_price"] for rcode, est in estimates.items()}

    @classmethod
    def _route_estimates_for_series(
        cls,
        db: Session,
        observation_date: datetime.date,
        advance_days: int,
        price_field: str,
        series_type: str = "HEADLINE",
        require_continuity: bool = True,
    ) -> Dict[str, Any]:
        """Returns full per-route estimator outputs for a given series filter.

        Single estimator pass behind both :meth:`get_route_representative_prices`
        and index/variance computation: CORE festival guard + continuity gate are
        applied identically so the published index and its bootstrap CI are
        measured over the *same* route basket. Keeps the rich estimator
        diagnostics (``carrier_fares``, ``carrier_count``, feed quality, ...) so
        variance estimation can resample the elementary route-horizon cells.
        """
        routes = db.query(Route).filter(Route.active).all()
        peak_set = None
        if series_type == "CORE":
            peak_set = CoreIndexFilter.peak_dates(db)

        estimates: Dict[str, Any] = {}
        series_name = "BASE_FARE" if price_field == "base_fare" else "TOTAL_PRICE"

        for route in routes:
            observations = (
                db.query(FareObservation)
                .filter(
                    FareObservation.route_id == route.id,
                    FareObservation.search_timestamp
                    >= datetime.datetime.combine(observation_date, datetime.time.min),
                    FareObservation.search_timestamp
                    <= datetime.datetime.combine(observation_date, datetime.time.max),
                    FareObservation.advance_purchase_days == advance_days,
                )
                .all()
            )
            if not observations:
                continue

            if series_type == "CORE":
                observations = CoreIndexFilter.filter_observations(observations, peak_set)
                if not observations:
                    continue
                if require_continuity:
                    if not CoreIndexFilter.route_has_continuity(
                        db, route.id, observation_date, series_name
                    ):
                        continue

            obs_dicts = [
                {
                    "carrier": str(o.airline_id),
                    "cabin_class": o.cabin_class,
                    "fare_family": o.fare_family,
                    "availability_status": o.availability_status,
                    "base_fare": o.base_fare,
                    "total_fare": o.total_fare,
                    "feed_type": getattr(o, "feed_type", "SYNTHETIC_BASELINE"),
                }
                for o in observations
            ]

            est = RepresentativePriceEstimator.estimate_route_price(
                observations=obs_dicts,
                price_field=price_field,
                estimator="JEVONS",  # IMF/ABS best practice for elementary indices
                cabin_class="ECONOMY",
                fare_family="BASIC",
                apply_waterfall=True,
                apply_outlier_filter=True,
            )
            if est and est.get("representative_price") is not None:
                estimates[route.route_code] = est

        return estimates

    @staticmethod
    def _route_cell_samples(estimates: Dict[str, Any]) -> Dict[str, List[float]]:
        """Extracts per-route elementary-cells (per-carrier minimum fares).

        Each cell is exactly the input to the Jevons geometric mean that feeds
        the national Laspeyres aggregation -- resampling these is the unit of
        bootstrap uncertainty quantification. Uses ``carrier_fares_for_variance``
        (the outlier-filtered set that actually produced ``representative_price``)
        rather than the raw ``carrier_fares`` -- otherwise a single MAD/IQR-excluded
        outlier bid would still get resampled into the published CI even though
        the point estimate itself never used it, producing a CI that doesn't
        describe the same estimator it's supposed to annotate.
        """
        samples: Dict[str, List[float]] = {}
        for rcode, est in estimates.items():
            if not est:
                continue
            carrier_fares = est.get("carrier_fares_for_variance") or est.get("carrier_fares") or {}
            fares = [float(f) for f in carrier_fares.values()]
            if fares:
                samples[rcode] = fares
        return samples

    @classmethod
    def _bootstrap_variance(
        cls,
        route_samples: Dict[str, List[float]],
        base_prices: Dict[str, float],
        route_weights: Dict[str, float],
        observed_index: float,
    ) -> Optional[Dict[str, Any]]:
        """Variance SE/CI for the national index, safe on degenerate cells.

        Honours ``settings.INDEX_VARIANCE_METHOD`` (config.py):
          * ``JACKKNIFE`` (default, NSO-standard) -- deterministic
            delete-one-route SE via ``jackknife_index_variance``.  Exact,
            seed-free, and (benchmark rung-4) ~50-90x cheaper than bootstrap
            for the same SE; no CI distribution is produced.
          * ``BOOTSTRAP`` -- Monte-Carlo percentile SE/CI via
            ``bootstrap_index_variance``; keep when a CI *distribution*
            (percentile tails) is published.

        Both rungs inherit the calculator's geometric-mean cell handling, so
        switching methods can never change the point value being annotated.
        """
        try:
            method = getattr(
                settings, "INDEX_VARIANCE_METHOD", "JACKKNIFE"
            ).upper()
            if method == "JACKKNIFE":
                # Jackknife consumes one geometric-mean price *per route* (the
                # Jevons elementary cell), not per-carrier lists.
                route_prices = {
                    rcode: float(np.exp(np.mean(np.log([p for p in v if p > 0]))))
                    for rcode, v in route_samples.items()
                    if v and any(p > 0 for p in v)
                }
                return IndexVarianceEstimator.jackknife_index_variance(
                    route_prices=route_prices,
                    base_prices=base_prices,
                    route_weights=route_weights,
                )
            return IndexVarianceEstimator.bootstrap_index_variance(
                route_samples=route_samples,
                base_prices=base_prices,
                route_weights=route_weights,
                observed_index=observed_index,
                n_bootstrap=settings.INDEX_BOOTSTRAP_REPLICATIONS,
                confidence_level=settings.INDEX_VARIANCE_CI_LEVEL,
                random_seed=getattr(settings, "INDEX_VARIANCE_SEED", None),
            )
        except IndexVarianceError:
            return None

    @classmethod
    def _calculate_index_quality(
        cls,
        current_prices: Dict[str, float],
        base_prices: Dict[str, float],
        nat_result: Dict[str, Any],
        current_estimates: Dict[str, Any],
        series_name: str,
        index_type: str,
        observation_date: datetime.date,
        db: Session,
    ) -> Dict[str, Any]:
        """Calculate comprehensive quality metrics for index governance."""
        total_routes = len(current_prices)
        real_base_routes = sum(1 for v in base_prices.values() if v is not None and v > 0)
        fallback_routes = total_routes - real_base_routes

        coverage_rate = nat_result.get("coverage_rate", 0.0)
        data_completeness = (total_routes / 10) * 100  # 10 total routes

        # Aggregate quality from per-route estimates
        carrier_diversity = 0
        feed_quality_sum = 0.0
        outlier_count = 0
        valid_estimates = 0

        for est in current_estimates.values():
            if est:
                carrier_diversity += est.get("carrier_count", 0)
                feed_quality_sum += est.get("feed_quality_score", 0.0)
                outlier_count += est.get("outlier_detection", {}).get("removed_count", 0)
                valid_estimates += 1

        avg_feed_quality = feed_quality_sum / valid_estimates if valid_estimates > 0 else 0.0
        avg_carrier_diversity = carrier_diversity / valid_estimates if valid_estimates > 0 else 0

        # Determine index status (EXPERIMENTAL -> BETA -> LIVE)
        if coverage_rate >= cls.MIN_COVERAGE_FOR_LIVE and total_routes >= cls.MIN_ROUTES_FOR_LIVE:
            index_status = "LIVE"
        elif coverage_rate >= cls.MIN_COVERAGE_FOR_BETA and total_routes >= cls.MIN_ROUTES_FOR_LIVE - 2:
            index_status = "BETA"
        else:
            index_status = "EXPERIMENTAL"

        # Composite quality score (0-100)
        quality_score = (
            coverage_rate * 0.3
            + min(data_completeness, 100) * 0.2
            + min(avg_feed_quality, 100) * 0.2
            + min(avg_carrier_diversity * 10, 100) * 0.15
            + (100 - min(outlier_count * 10, 100)) * 0.15
        )

        return {
            "index_status": index_status,
            "quality_score": round(quality_score, 1),
            "data_completeness": round(data_completeness, 1),
            "carrier_diversity": round(avg_carrier_diversity, 1),
            "feed_quality_score": round(avg_feed_quality, 1),
            "outlier_count": outlier_count,
            "fallback_routes": fallback_routes,
            "real_base_routes": real_base_routes,
        }

    @classmethod
    def _compute_28day_moving_average(
        cls,
        db: Session,
        series_name: str,
        index_type: str,
        observation_date: datetime.date,
        lead_time: int,
        route_id: Optional[int] = None,
    ) -> Optional[float]:
        """Compute 28-day moving average (Skytra methodology)."""
        start_date = observation_date - datetime.timedelta(days=cls.MOVING_AVG_WINDOW - 1)
        query = db.query(IndexValue).filter(
            IndexValue.index_series == series_name,
            IndexValue.index_type == index_type,
            IndexValue.lead_time_days == lead_time,
            IndexValue.period_start >= start_date,
            IndexValue.period_start <= observation_date,
        )
        if route_id is not None:
            query = query.filter(IndexValue.route_id == route_id)
        else:
            query = query.filter(IndexValue.route_id.is_(None))

        values = [r.index_value for r in query.all() if r.index_value > 0]
        if len(values) < 5:  # Need minimum data points
            return None
        return round(float(np.mean(values)), 2)

    @classmethod
    def _compute_index_divisor(
        cls,
        db: Session,
        series_name: str,
        index_type: str,
        observation_date: datetime.date,
        lead_time: int,
        current_index: float,
        route_id: Optional[int] = None,
    ) -> float:
        """
        Compute index divisor for continuity (Skytra methodology).
        Divisor adjusts to maintain continuity across events (methodology changes, reweighting).
        """
        # Get previous divisor
        prev_date = observation_date - datetime.timedelta(days=1)
        query = db.query(IndexValue).filter(
            IndexValue.index_series == series_name,
            IndexValue.index_type == index_type,
            IndexValue.lead_time_days == lead_time,
            IndexValue.period_start == prev_date,
        )
        if route_id is not None:
            query = query.filter(IndexValue.route_id == route_id)
        else:
            query = query.filter(IndexValue.route_id.is_(None))

        prev_rec = query.first()
        if prev_rec and prev_rec.index_divisor:
            return prev_rec.index_divisor

        # First record or divisor reset: start at 1.0
        return 1.0

    @classmethod
    def calculate_day_indices(
        cls,
        db: Session,
        observation_date: datetime.date,
        base_date: Optional[datetime.date] = None,
        methodology_version: str = "APIX-2.0",
        weight_version: str = "DGCA_2026_V1",
        persist: bool = True,
        compute_core: bool = True,
        base_prices_cache: Optional[Dict[str, Dict[int, Dict[str, float]]]] = None,
    ) -> List[IndexValue]:
        """
        Calculates and persists all daily indices for an observation date:
        - Headline Index (T+15 Anchor) for BASE_FARE and TOTAL_PRICE
        - Unpooled Lead-Time Sub-Indices (T+1, T+7, T+15, T+30, T+45)
        - Route-level indices
        - Computes 1D, 7D, 30D percentage changes
        - 28-day moving average (Skytra)
        - Index divisor for continuity (Skytra)
        - Quality metrics & governance flags (FAX/Skytra)
        - Spot window tracking (BLS/CPI)
        """

        if base_date is None:
            base_date = datetime.date(2026, 8, 1)

        route_weights = DGCAWeightEngine.get_active_weights(db, target_date=observation_date)
        if not route_weights:
            all_w = db.query(RouteWeight, Route).join(Route, RouteWeight.route_id == Route.id).all()
            route_weights = {r.route_code: rw.weight for rw, r in all_w}

        total_w = sum(route_weights.values())
        if total_w > 0:
            route_weights = {r: w / total_w for r, w in route_weights.items()}

        routes = db.query(Route).filter(Route.active).all()
        route_id_map = {r.route_code: r.id for r in routes}

        created_index_records: List[IndexValue] = []

        for series_name in cls.PRICE_SERIES:
            field_name = "base_fare" if series_name == "BASE_FARE" else "total_fare"

            for horizon in cls.HORIZONS:
                is_headline = horizon == cls.HEADLINE_HORIZON
                index_type = "HEADLINE_T15" if is_headline else f"SUB_T{horizon}"

                # 1. Single estimator pass: representative prices, quality
                #    diagnostics AND the elementary cells for variance bootstrap.
                current_estimates = cls._route_estimates_for_series(
                    db, observation_date, advance_days=horizon, price_field=field_name
                )
                current_prices = {
                    rcode: est["representative_price"]
                    for rcode, est in current_estimates.items()
                }
                route_samples = cls._route_cell_samples(current_estimates)

                # 2. Base period prices -- precomputed once per (series, horizon) for a
                #    historical backfill (identical for every observation date),
                #    otherwise computed on demand.
                base_prices = (
                    base_prices_cache.get(series_name, {}).get(horizon)
                    if base_prices_cache
                    else None
                )
                if base_prices is None:
                    base_prices = cls.get_route_representative_prices(
                        db, base_date, advance_days=horizon, price_field=field_name
                    )
                real_base_routes = {
                    rcode for rcode, rp in base_prices.items() if rp is not None and rp > 0
                }

                # Fallback if base date prices equal to current or missing
                for rcode, cp in current_prices.items():
                    if rcode not in base_prices or base_prices[rcode] <= 0:
                        base_prices[rcode] = cp

                if not current_prices:
                    types = [index_type, "ROUTE_LEVEL"] if is_headline else [index_type]
                    db.query(IndexValue).filter(
                        IndexValue.index_series == series_name,
                        IndexValue.index_type.in_(types),
                        IndexValue.period_start == observation_date,
                    ).delete()
                    continue

                # A national index backed ONLY by fallback base prices (= current)
                # is meaningless (always 100.0) and would pollute the published series.
                if observation_date != base_date and not real_base_routes:
                    continue

                # 3. Calculate National Index
                nat_result = AirfareIndexEngine.calculate_national_index(
                    route_prices=current_prices,
                    base_prices=base_prices,
                    route_weights=route_weights,
                )

                # 3b. Bootstrap variance of the index (NSO-standard SE + CI)
                variance = cls._bootstrap_variance(
                    route_samples=route_samples,
                    base_prices=base_prices,
                    route_weights=route_weights,
                    observed_index=nat_result["index_value"],
                )

                # 4. Compute percentage deltas
                deltas = cls._calculate_deltas(
                    db=db,
                    current_value=nat_result["index_value"],
                    series_name=series_name,
                    index_type=index_type,
                    lead_time=horizon,
                    observation_date=observation_date,
                    route_id=None,
                )

                # 5. Quality metrics & governance
                quality = cls._calculate_index_quality(
                    current_prices, base_prices, nat_result, current_estimates, series_name, index_type, observation_date, db
                )

                # 6. 28-day moving average
                moving_avg = cls._compute_28day_moving_average(
                    db, series_name, index_type, observation_date, horizon
                )

                # 7. Index divisor for continuity
                index_divisor = cls._compute_index_divisor(
                    db, series_name, index_type, observation_date, horizon, nat_result["index_value"]
                )

                # 8. Spot window (BLS-style: fixed advance booking window)
                spot_start = observation_date - datetime.timedelta(days=cls.SPOT_WINDOW_DAYS)
                spot_end = observation_date - datetime.timedelta(days=3)

                # 9. Persist National Index record
                db.query(IndexValue).filter(
                    IndexValue.index_series == series_name,
                    IndexValue.index_type == index_type,
                    IndexValue.period_start == observation_date,
                    IndexValue.route_id.is_(None),
                ).delete()

                nat_record = IndexValue(
                    index_series=series_name,
                    index_type=index_type,
                    lead_time_days=horizon,
                    period_start=observation_date,
                    period_end=observation_date,
                    route_id=None,
                    index_value=nat_result["index_value"],
                    daily_change_pct=deltas["1d"],
                    weekly_change_pct=deltas["7d"],
                    monthly_change_pct=deltas["30d"],
                    coverage_rate=nat_result["coverage_rate"],
                    is_low_coverage=nat_result["is_low_coverage"],
                    methodology_version=methodology_version,
                    weight_version=weight_version,
                    calculated_at=utcnow(),
                    # Quality & governance
                    index_status=quality["index_status"],
                    quality_score=quality["quality_score"],
                    data_completeness=quality["data_completeness"],
                    carrier_diversity=quality["carrier_diversity"],
                    feed_quality_score=quality["feed_quality_score"],
                    outlier_count=quality["outlier_count"],
                    index_divisor=index_divisor,
                    moving_avg_28d=moving_avg,
                    spot_window_start=spot_start,
                    spot_window_end=spot_end,
                    # Variance estimation (JACKKNIFE SE, or BOOTSTRAP SE + percentile CI)
                    standard_error=variance.get("standard_error") if variance else None,
                    index_ci_lower=variance.get("ci_lower") if variance else None,
                    index_ci_upper=variance.get("ci_upper") if variance else None,
                    bootstrap_replications=variance.get("n_bootstrap") if variance else None,
                    variance_method=variance.get("method") if variance else None,
                )
                db.add(nat_record)
                created_index_records.append(nat_record)

                # 10. If headline horizon, also persist route-level indices
                if is_headline:
                    for rcode, r_idx in nat_result["route_indices"].items():
                        rid = route_id_map.get(rcode)
                        if not rid:
                            continue

                        r_deltas = cls._calculate_deltas(
                            db=db,
                            current_value=r_idx,
                            series_name=series_name,
                            index_type="ROUTE_LEVEL",
                            lead_time=horizon,
                            observation_date=observation_date,
                            route_id=rid,
                        )

                        # Route-level bootstrap CI from the Jevons cell sample
                        route_variance = None
                        route_sample = route_samples.get(rcode)
                        if route_sample and base_prices.get(rcode, 0) > 0:
                            try:
                                route_variance = (
                                    IndexVarianceEstimator.bootstrap_route_index_variance(
                                        route_sample=route_sample,
                                        base_price=base_prices[rcode],
                                        observed_index=r_idx,
                                        n_bootstrap=settings.INDEX_BOOTSTRAP_REPLICATIONS,
                                        confidence_level=settings.INDEX_VARIANCE_CI_LEVEL,
                                        random_seed=getattr(settings, "INDEX_VARIANCE_SEED", None),
                                    )
                                )
                            except IndexVarianceError:  # pragma: no cover - defensive
                                route_variance = None

                        # Route-level quality (simplified)
                        route_cov = nat_result.get("coverage_rate", 100.0)
                        route_quality = {
                            "index_status": "LIVE" if route_cov >= 90 else "BETA",
                            "quality_score": 90.0 if route_cov >= 90 else 70.0,
                            "data_completeness": 100.0,
                            "carrier_diversity": 1,
                            "feed_quality_score": 80.0,
                            "outlier_count": 0,
                            "index_divisor": 1.0,
                            "moving_avg_28d": cls._compute_28day_moving_average(
                                db, series_name, "ROUTE_LEVEL", observation_date, horizon, rid
                            ),
                            "spot_window_start": spot_start,
                            "spot_window_end": spot_end,
                        }

                        db.query(IndexValue).filter(
                            IndexValue.index_series == series_name,
                            IndexValue.index_type == "ROUTE_LEVEL",
                            IndexValue.period_start == observation_date,
                            IndexValue.route_id == rid,
                        ).delete()

                        route_rec = IndexValue(
                            index_series=series_name,
                            index_type="ROUTE_LEVEL",
                            lead_time_days=horizon,
                            period_start=observation_date,
                            period_end=observation_date,
                            route_id=rid,
                            index_value=r_idx,
                            daily_change_pct=r_deltas["1d"],
                            weekly_change_pct=r_deltas["7d"],
                            monthly_change_pct=r_deltas["30d"],
                            coverage_rate=100.0,
                            is_low_coverage=False,
                            methodology_version=methodology_version,
                            weight_version=weight_version,
                            calculated_at=utcnow(),
                            standard_error=route_variance["standard_error"]
                            if route_variance
                            else None,
                            index_ci_lower=route_variance["ci_lower"] if route_variance else None,
                            index_ci_upper=route_variance["ci_upper"] if route_variance else None,
                            bootstrap_replications=route_variance["n_bootstrap"]
                            if route_variance
                            else None,
                            variance_method=route_variance["method"] if route_variance else None,
                            **route_quality,
                        )
                        db.add(route_rec)
                        created_index_records.append(route_rec)

        # ---- Dual-Series: CORE headline (volatility-guarded version of T+15) ----
        if compute_core:
            core_records = cls._calculate_core_headline(
                db,
                observation_date=observation_date,
                base_date=base_date,
                route_weights=route_weights,
                methodology_version=methodology_version,
                weight_version=weight_version,
            )
            created_index_records.extend(core_records)

        if persist:
            db.commit()
        else:
            db.rollback()
        return created_index_records

    @classmethod
    def _find_core_anchor(
        cls,
        db: Session,
        base_date: datetime.date,
        horizon: int,
        price_field: str,
        max_lookback: int = 21,
        observation_date: Optional[datetime.date] = None,
    ) -> tuple:
        """Finds the nearest day whose T+15 travel window is not excluded by the
        CORE festival guard and returns that day with its CORE representative
        prices. Searches forward first (the canonical base day's travel window
        often falls on a festival), then backward up to ``max_lookback`` days.
        Never uses a day later than ``observation_date`` to avoid future leakage.
        Returns ``(base_date, {})`` if none found.
        """
        from packages.statistics.core_filter import CoreIndexFilter

        peak_set = CoreIndexFilter.peak_dates(db)
        candidates: List[datetime.date] = []
        horizon_span = datetime.timedelta(days=horizon)
        for step in range(max_lookback + 1):
            candidates.append(base_date + datetime.timedelta(days=step))
            candidates.append(base_date - datetime.timedelta(days=step))

        for day in candidates:
            # never anchor on a day later than the day being indexed
            if observation_date is not None and day > observation_date:
                continue
            reps = cls.get_route_representative_prices(
                db,
                day,
                advance_days=horizon,
                price_field=price_field,
                series_type="CORE",
                require_continuity=False,
            )
            if not reps:
                continue
            travel = day + horizon_span
            if travel in peak_set:
                continue
            return day, reps
        return base_date, {}

    @classmethod
    def _calculate_core_headline(
        cls,
        db: Session,
        observation_date: datetime.date,
        base_date: datetime.date,
        route_weights: Dict[str, float],
        methodology_version: str = "APIX-2.0",
        weight_version: str = "DGCA_2026_V1",
    ) -> List[IndexValue]:
        """Computes the CORE T+15 headline index: the same Jevons anchor computed
        on the volatility-guarded observation set (festival windows excluded,
        continuity-guarded routes only).

        The CORE series forms the second line of the Observatory's dual-series
        HEADLINE/CORE design: it isolates underlying structural fare inflation
        from festive demand spikes.
        """
        created: List[IndexValue] = []

        for series_name in cls.PRICE_SERIES:
            field_name = "base_fare" if series_name == "BASE_FARE" else "total_fare"

            core_current_estimates = cls._route_estimates_for_series(
                db,
                observation_date,
                advance_days=cls.HEADLINE_HORIZON,
                price_field=field_name,
                series_type="CORE",
                require_continuity=True,
            )
            if not core_current_estimates:
                continue
            core_current = {
                rcode: est["representative_price"]
                for rcode, est in core_current_estimates.items()
            }

            core_base = cls.get_route_representative_prices(
                db,
                base_date,
                advance_days=cls.HEADLINE_HORIZON,
                price_field=field_name,
                series_type="CORE",
                require_continuity=False,
            )
            core_anchor = base_date
            if not core_base:
                # The canonical base day's T+15 travel window may itself fall on a
                # festival/peak date (e.g. 2026-08-01 anchors on 15-Aug travel) and
                # be excluded by the CORE guard. Re-anchor on the nearest day
                # whose T+15 travel window is festival-free.
                core_anchor, core_base = cls._find_core_anchor(
                    db, base_date, cls.HEADLINE_HORIZON, field_name,
                    observation_date=observation_date,
                )
            for rcode, cp in core_current.items():
                if rcode not in core_base or core_base[rcode] <= 0:
                    core_base[rcode] = cp

            # Safeguard: a CORE index backed ONLY by fallback base (= current)
            # prices is always 100.0 and adds no signal. Skip when no route had a
            # genuine (non-fallback) festival-free base reference.
            if not any(
                rcode in core_base and core_base[rcode] != core_current[rcode]
                for rcode in core_current
            ):
                continue

            nat = AirfareIndexEngine.calculate_national_index(
                route_prices=core_current,
                base_prices=core_base,
                route_weights=route_weights,
            )

            core_variance = cls._bootstrap_variance(
                route_samples=cls._route_cell_samples(core_current_estimates),
                base_prices=core_base,
                route_weights=route_weights,
                observed_index=nat["index_value"],
            )

            deltas = cls._calculate_deltas(
                db, nat["index_value"], series_name, "HEADLINE_T15",
                cls.HEADLINE_HORIZON, observation_date, route_id=None,
            )
            quality = cls._calculate_index_quality(
                core_current, core_base, nat, {}, series_name,
                "HEADLINE_T15", observation_date, db,
            )
            moving_avg = cls._compute_28day_moving_average(
                db, series_name, "HEADLINE_T15", observation_date, cls.HEADLINE_HORIZON
            )
            spot_start = observation_date - datetime.timedelta(days=cls.SPOT_WINDOW_DAYS)
            spot_end = observation_date - datetime.timedelta(days=3)

            db.query(IndexValue).filter(
                IndexValue.index_series == series_name,
                IndexValue.index_type == "HEADLINE_T15",
                IndexValue.series_type == "CORE",
                IndexValue.period_start == observation_date,
                IndexValue.route_id.is_(None),
            ).delete()

            rec = IndexValue(
                index_series=series_name,
                series_type="CORE",
                index_type="HEADLINE_T15",
                lead_time_days=cls.HEADLINE_HORIZON,
                period_start=observation_date,
                period_end=observation_date,
                route_id=None,
                index_value=nat["index_value"],
                daily_change_pct=deltas["1d"],
                weekly_change_pct=deltas["7d"],
                monthly_change_pct=deltas["30d"],
                coverage_rate=nat["coverage_rate"],
                is_low_coverage=nat["is_low_coverage"],
                methodology_version=methodology_version,
                weight_version=weight_version,
                calculated_at=utcnow(),
                index_status=quality["index_status"],
                quality_score=quality["quality_score"],
                data_completeness=quality["data_completeness"],
                carrier_diversity=quality["carrier_diversity"],
                feed_quality_score=quality["feed_quality_score"],
                outlier_count=quality["outlier_count"],
                index_divisor=cls._compute_index_divisor(
                    db, series_name, "HEADLINE_T15", observation_date,
                    cls.HEADLINE_HORIZON, nat["index_value"],
                ),
                moving_avg_28d=moving_avg,
                spot_window_start=spot_start,
                spot_window_end=spot_end,
                standard_error=core_variance.get("standard_error") if core_variance else None,
                index_ci_lower=core_variance.get("ci_lower") if core_variance else None,
                index_ci_upper=core_variance.get("ci_upper") if core_variance else None,
                bootstrap_replications=core_variance.get("n_bootstrap") if core_variance else None,
                variance_method=core_variance.get("method") if core_variance else None,
            )
            db.add(rec)
            created.append(rec)

        return created

    @classmethod
    def _calculate_deltas(
        cls,
        db: Session,
        current_value: float,
        series_name: str,
        index_type: str,
        lead_time: int,
        observation_date: datetime.date,
        route_id: Optional[int] = None,
    ) -> Dict[str, Optional[float]]:
        """Calculates 1D, 7D, and 30D percentage deltas relative to historical index values."""
        deltas: Dict[str, Optional[float]] = {"1d": None, "7d": None, "30d": None}

        for delta_key, days_back in [("1d", 1), ("7d", 7), ("30d", 30)]:
            prior_date = observation_date - datetime.timedelta(days=days_back)
            query = db.query(IndexValue).filter(
                IndexValue.index_series == series_name,
                IndexValue.index_type == index_type,
                IndexValue.lead_time_days == lead_time,
                IndexValue.period_start == prior_date,
            )
            if route_id is not None:
                query = query.filter(IndexValue.route_id == route_id)
            else:
                query = query.filter(IndexValue.route_id.is_(None))

            prior_rec = query.first()
            if prior_rec and prior_rec.index_value > 0:
                pct_change = (
                    (current_value - prior_rec.index_value) / prior_rec.index_value
                ) * 100.0
                deltas[delta_key] = round(pct_change, 2)

        return deltas

    @classmethod
    def compute_historical_index_range(
        cls,
        db: Session,
        start_date: datetime.date,
        end_date: datetime.date,
        persist: bool = True,
    ) -> int:
        """Batch computes daily indices across a date range.

        Base-period prices depend only on ``start_date`` (not on the observation
        date), so they are estimated once per series/horizon and reused across
        every day instead of being recomputed in the hot loop.
        """
        base_prices_cache: Dict[str, Dict[int, Dict[str, float]]] = {}
        for series_name in cls.PRICE_SERIES:
            field_name = "base_fare" if series_name == "BASE_FARE" else "total_fare"
            base_prices_cache[series_name] = {}
            for horizon in cls.HORIZONS:
                base_prices_cache[series_name][horizon] = {
                    rcode: est["representative_price"]
                    for rcode, est in cls._route_estimates_for_series(
                        db, start_date, advance_days=horizon, price_field=field_name
                    ).items()
                }

        current = start_date
        total_computed = 0

        while current <= end_date:
            recs = cls.calculate_day_indices(
                db,
                observation_date=current,
                base_date=start_date,
                persist=persist,
                base_prices_cache=base_prices_cache,
            )
            total_computed += len(recs)
            current += datetime.timedelta(days=1)

        return total_computed
