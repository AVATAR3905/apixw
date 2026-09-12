"""Geometry-based clustering of OCR tokens into fare-card groups.

Flight-results pages render each offer as a card: a cluster of words sharing a
horizontal band (row) and close x-overlap. Rather than a document pipeline,
we group tokens by proximity of their y-centroids — simple, deterministic,
and good enough to turn flat OCR output back into per-card records.
"""

import statistics
from typing import Any, List, NamedTuple


class OCRToken(NamedTuple):
    text: str
    bbox: List[float]  # [x1, y1, x2, y2]
    score: float = 1.0

    @property
    def y_center(self) -> float:
        return float((self.bbox[1] + self.bbox[3]) / 2.0)

    @property
    def x_center(self) -> float:
        return float((self.bbox[0] + self.bbox[2]) / 2.0)

    @property
    def height(self) -> float:
        return max(1.0, float(self.bbox[3] - self.bbox[1]))

    def to_dict(self) -> dict:
        return {"text": self.text, "bbox": self.bbox, "score": self.score}


def token_from_ocr_line(line: Any) -> OCRToken:
    """Adapts a PaddleOCR 2.x-style line ``[box, (text, score)]`` into an OCRToken."""
    box, text_score = line
    x1 = min(p[0] for p in box)
    y1 = min(p[1] for p in box)
    x2 = max(p[0] for p in box)
    y2 = max(p[1] for p in box)
    text, score = (
        text_score if isinstance(text_score, (list, tuple)) and text_score else (text_score, 1.0)
    )
    return OCRToken(text=str(text), bbox=[x1, y1, x2, y2], score=float(score))


def tokens_from_paddle_result(res: dict) -> List[OCRToken]:
    """Build OCRTokens from a PaddleOCR 3.x ``result.json['res']`` dict.

    Keys: ``rec_texts`` (str list), ``rec_scores`` (float list), ``rec_boxes``
    (``[x1, y1, x2, y2]`` list). Missing geometry falls back to a neutral box so
    downstream clustering never blows up.
    """
    texts = res.get("rec_texts") or []
    scores = res.get("rec_scores") or []
    boxes = res.get("rec_boxes") or []
    tokens: List[OCRToken] = []
    for i, text in enumerate(texts):
        score = float(scores[i]) if i < len(scores) else 1.0
        box = boxes[i] if i < len(boxes) else [0.0, 0.0, 1.0, 1.0]
        if (
            isinstance(box, (list, tuple)) and box and isinstance(box[0], (list, tuple))
        ):  # 4-corner polygon
            x1, y1, x2, y2 = (
                min(p[0] for p in box),
                min(p[1] for p in box),
                max(p[0] for p in box),
                max(p[1] for p in box),
            )
        elif len(box) == 4:
            x1, y1, x2, y2 = (float(v) for v in box)
        else:
            x1, y1, x2, y2 = 0.0, 0.0, 1.0, 1.0
        tokens.append(OCRToken(text=str(text), bbox=[x1, y1, x2, y2], score=score))
    return tokens


class LayoutClusterer:
    """Groups OCR tokens into fare cards by vertical banding."""

    @staticmethod
    def cluster(tokens: List[OCRToken]) -> List[List[OCRToken]]:
        if not tokens:
            return []
        order = sorted(tokens, key=lambda t: t.y_center)
        heights = [t.height for t in order]
        median_h = statistics.median(heights)
        gap_tolerance = max(12.0, median_h * 1.8)

        clusters: List[List[OCRToken]] = []
        current = [order[0]]
        prev_y = order[0].y_center
        for token in order[1:]:
            if token.y_center - prev_y <= gap_tolerance:
                current.append(token)
            else:
                clusters.append(current)
                current = [token]
            prev_y = token.y_center
        clusters.append(current)
        return clusters

    @classmethod
    def cards(cls, tokens: List[OCRToken]) -> List[dict]:
        """Cluster tokens and give each card a stable index + joined text."""
        results = []
        for idx, cluster in enumerate(cls.cluster(tokens)):
            cluster = sorted(cluster, key=lambda t: t.x_center)
            results.append(
                {
                    "card_index": idx,
                    "text": " ".join(t.text for t in cluster),
                    "tokens": [t.to_dict() for t in cluster],
                    "y_center": statistics.mean(t.y_center for t in cluster),
                }
            )
        return results
