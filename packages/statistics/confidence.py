"""Two-stage confidence engine for fare observations.

Stage 1: per-record composite =  QualityScore x ExtractionMethodWeight
Stage 2: cross-source agreement bonus (consensus across platforms within a
tolerance band raises confidence; disagreement lowers it).

Composite scores map to operational bands (HIGH / MEDIUM / LOW) using
configurable thresholds so the acceptance policy can be tuned without code.
"""

import statistics
from typing import Dict, List

from packages.shared.config import settings

# Base trust weight per extraction method (0..1). Non-network/simulated methods
# are deliberately discounted so the index never treats calibrated data as live.
METHOD_WEIGHTS: Dict[str, float] = {
    "NETWORK_XHR": 0.98,
    "EMBEDDED": 0.97,
    "NETWORK": 0.96,
    "DOM_BROWSER": 0.95,
    "RPC": 0.94,
    "LLM": 0.93,
    "VLM": 0.90,
    "OCR": 0.85,
    "CALIBRATED_MODEL": 0.60,
    "SYNTHETIC": 0.50,
}
DEFAULT_METHOD_WEIGHT = 0.50

AGREEMENT_TOLERANCE = 0.10  # +-10% around median counts as consensus


class ConfidenceService:
    """Computes and bands composite confidence scores."""

    @staticmethod
    def method_weight(extraction_method: str) -> float:
        method = (extraction_method or "").upper()
        return METHOD_WEIGHTS.get(method, DEFAULT_METHOD_WEIGHT)

    @staticmethod
    def composite(quality_score: float, extraction_method: str, agreement: float = 1.0) -> float:
        """Combine quality, extraction trust, and cross-source agreement into a 0..100 score."""
        quality = max(0.0, min(100.0, float(quality_score)))
        agreement = max(0.0, min(1.0, float(agreement)))
        base = quality * ConfidenceService.method_weight(extraction_method)
        adjusted = base * (0.95 + 0.10 * agreement)
        return round(max(0.0, min(100.0, adjusted)), 2)

    @staticmethod
    def band(composite: float) -> str:
        """High/Medium/Low operational band driven by settings thresholds."""
        if composite >= settings.CONFIDENCE_HIGH_MIN:
            return "HIGH"
        if composite >= settings.CONFIDENCE_MEDIUM_MIN:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def cross_source_agreement(quotes: List[Dict]) -> float:
        """Fraction of quotes within +-10% of the platform median total fare."""
        fares = [float(q["total_fare"]) for q in quotes if q.get("total_fare")]
        if not fares:
            return 0.0
        median = statistics.median(fares)
        if median <= 0:
            return 0.0
        agreeing = sum(1 for f in fares if abs(f - median) / median <= AGREEMENT_TOLERANCE)
        return round(agreeing / len(fares), 4)

    @classmethod
    def score_quotes(cls, quotes: List[Dict], extraction_method: str = "") -> List[Dict]:
        """Enrich a list of quotes with per-record composite confidence metadata."""
        agreement = cls.cross_source_agreement(quotes)
        scored = []
        for q in quotes:
            method = q.get("extraction_method") or extraction_method
            qscore = float(q.get("quality_score", 100.0))
            composite = cls.composite(qscore, method, agreement)
            scored.append(
                {
                    **q,
                    "confidence_score": composite,
                    "confidence_band": cls.band(composite),
                    "cross_source_agreement": agreement,
                }
            )
        return scored
