"""Fast unit tests for paddleocr-3.x result adaptation and VLM field parsing."""

from packages.ai.openrouter_vision import _fields_from_answer
from services.extraction.layout_clusterer import tokens_from_paddle_result
from services.extraction.vlm_service import VLMService, _PaddleOCRVLBackend


def test_tokens_from_paddle_result_maps_rec_rows():
    res = {
        "rec_texts": ["DEL -> BOM", "INR 4,250"],
        "rec_scores": [0.99, 0.98],
        "rec_boxes": [[10, 20, 200, 50], [10, 60, 160, 90]],
    }
    tokens = tokens_from_paddle_result(res)
    assert [t.text for t in tokens] == ["DEL -> BOM", "INR 4,250"]
    assert tokens[0].bbox == [10.0, 20.0, 200.0, 50.0]
    assert tokens[0].score == 0.99


def test_tokens_from_paddle_result_handles_missing_geometry():
    tokens = tokens_from_paddle_result({"rec_texts": ["6E-204"]})
    assert len(tokens) == 1
    assert tokens[0].text == "6E-204"
    assert tokens[0].score == 1.0


def test_tokens_from_paddle_result_handles_polygon_boxes():
    res = {
        "rec_texts": ["INR 1,999"],
        "rec_boxes": [[[0, 10], [80, 10], [80, 40], [0, 40]]],
    }
    tokens = tokens_from_paddle_result(res)
    assert tokens[0].bbox == [0.0, 10.0, 80.0, 40.0]


def test_vlm_strips_html_entities_before_route_match():
    fields = _PaddleOCRVLBackend._parse_fields("<table><tr><td>DEL -&gt; BOM</td></tr></table>")
    assert fields["origin"] == "DEL"
    assert fields["destination"] == "BOM"


def test_vlm_parses_price_without_entity_text():
    fields = _PaddleOCRVLBackend._parse_fields("INR 4,250")
    assert fields["price"] == 4250.0


def test_vlm_parses_json_free_markdown_blob():
    blob = "route header DEL -&gt; BOM\nfares INR 1,299\n"
    fields = _PaddleOCRVLBackend._parse_fields(blob)
    assert fields == {"origin": "DEL", "destination": "BOM", "price": 1299.0}


def test_vlm_extracts_full_fare_record():
    blob = (
        "<table><tr><td>DEL -&gt; BOM</td></tr>"
        "<tr><td>IndiGo 6E-204</td></tr>"
        "<tr><td>INR 4,250</td></tr>"
        "<tr><td>Dept 06:40 Arr 08:55</td></tr></table>"
    )
    fields = _PaddleOCRVLBackend._parse_fields(blob)
    assert fields == {
        "origin": "DEL",
        "destination": "BOM",
        "price": 4250.0,
        "airline": "6E",
        "airline_name": "IndiGo",
        "flight_number": "6E-204",
        "departure_time": "06:40",
        "arrival_time": "08:55",
    }


def test_openrouter_vision_parses_json_answer():
    payload = (
        '```json\n{"price": 4250, "origin": "DEL", "destination": "BOM",'
        ' "airline": "6E", "flight_number": "6E-204",'
        ' "departure_time": "06:40", "arrival_time": "08:55",'
        ' "stops": 0, "duration_minutes": 135, "travel_date": "2026-09-14"}\n```'
    )
    assert _fields_from_answer(payload) == {
        "price": 4250.0,
        "origin": "DEL",
        "destination": "BOM",
        "airline": "6E",
        "flight_number": "6E-204",
        "departure_time": "06:40",
        "arrival_time": "08:55",
        "stops": 0,
        "duration_minutes": 135,
        "travel_date": "2026-09-14",
    }


def test_openrouter_vision_parses_nested_and_plain_json():
    nested = '{"result": [{"data": {"total_fare": "INR 4,250", "from": "DEL", "to": "BOM"}}]}'
    assert _fields_from_answer(nested)["price"] == 4250.0
    assert _fields_from_answer(nested)["origin"] == "DEL"
    plain = '{"fare": 1299.0, "date": "2026-09-14"}'
    assert _fields_from_answer(plain)["price"] == 1299.0


def test_vlm_service_default_backend_reads_env():
    import os

    old = os.environ.get("EXTRACTION_VLM_BACKEND")
    os.environ["EXTRACTION_VLM_BACKEND"] = "openrouter"
    try:
        svc = VLMService()
        assert svc.prefer == "openrouter"
        assert "openrouter" in svc.backends
    finally:
        if old is None:
            os.environ.pop("EXTRACTION_VLM_BACKEND", None)
        else:
            os.environ["EXTRACTION_VLM_BACKEND"] = old
