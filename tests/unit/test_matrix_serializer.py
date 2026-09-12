"""Unit tests for ObservatoryMatrixSerializer."""

from database.session import SessionLocal
from packages.ai.matrix_serializer import ObservatoryMatrixSerializer


def test_matrix_serializer_digest():
    """Verifies that all 5 statistical matrices are compiled and sanitized."""
    db = SessionLocal()
    try:
        digest = ObservatoryMatrixSerializer.compile_full_matrix_digest(db, target_route="DEL-BOM")

        assert "matrix_1_headline" in digest
        assert "matrix_2_carrier_inflation" in digest
        assert "matrix_3_corridor_volatility" in digest
        assert "matrix_4_lead_time_yield" in digest
        assert "matrix_5_macro_fuel" in digest

        # Verify Matrix 1
        h = digest["matrix_1_headline"]
        assert h["current_index"] > 0
        assert "dgca_basket_weights_pct" in h

        # Verify Matrix 2
        c = digest["matrix_2_carrier_inflation"]
        assert "carriers" in c
        assert len(c["carriers"]) >= 4

        # Verify Matrix 3
        v = digest["matrix_3_corridor_volatility"]
        assert "corridors" in v
        assert len(v["corridors"]) > 0

        # Verify Matrix 5 non-causal rule
        f = digest["matrix_5_macro_fuel"]
        assert "non_causal_rule" in f
        assert "hedging" in f["non_causal_rule"].lower()

        # Verify formatted prompt text
        text = ObservatoryMatrixSerializer.format_matrices_as_system_text(db)
        assert "MATRIX 1: NATIONAL LASPEYRES HEADLINE" in text
        assert "MATRIX 2: CARRIER-WISE INFLATION" in text
        assert "MATRIX 5: MACRO JET FUEL" in text
    finally:
        db.close()
